#include <Uefi.h>

#include <Library/BaseLib.h>
#include <Library/BaseMemoryLib.h>
#include <Library/DevicePathLib.h>
#include <Library/UefiBootServicesTableLib.h>
#include <Library/UefiLib.h>

#include <Guid/EventGroup.h>
#include <Guid/Fdt.h>
#include <Guid/LinuxEfiInitrdMedia.h>

#include <Protocol/DevicePath.h>
#include <Protocol/LoadFile2.h>

#define XNUP_MAGIC        0x50554E58U
#define PAYLOAD_BASE      0xF0000000ULL
#define PAYLOAD_MAX_SIZE  0x04000000U
#define CMDLINE_MAX_SIZE  1024

typedef struct {
  UINT32          Magic;
  UINT32          Size;
} XNUP_HEADER;

typedef struct {
  CHAR8           Name[16];
  UINT32          Size;
  UINT32          Reserved;
} XNUP_ENTRY;

typedef struct {
  CONST UINT8     *Image;
  UINTN           ImageSize;
  CONST UINT8     *Dtb;
  UINTN           DtbSize;
  CONST UINT8     *Ramdisk;
  UINTN           RamdiskSize;
  CONST CHAR8     *Cmdline;
} XNUP_PAYLOAD;

typedef struct {
  VENDOR_DEVICE_PATH        VendorMediaNode;
  EFI_DEVICE_PATH_PROTOCOL  EndNode;
} RAMDISK_DEVICE_PATH;

STATIC CONST RAMDISK_DEVICE_PATH  mRamdiskDevicePath = {
  {
    {
      MEDIA_DEVICE_PATH,
      MEDIA_VENDOR_DP,
      {
        (UINT8)sizeof (VENDOR_DEVICE_PATH),
        (UINT8)(sizeof (VENDOR_DEVICE_PATH) >> 8)
      }
    },
    LINUX_EFI_INITRD_MEDIA_GUID
  },
  {
    END_DEVICE_PATH_TYPE,
    END_ENTIRE_DEVICE_PATH_SUBTYPE,
    {
      (UINT8)sizeof (EFI_DEVICE_PATH_PROTOCOL),
      (UINT8)(sizeof (EFI_DEVICE_PATH_PROTOCOL) >> 8)
    }
  }
};

STATIC VOID                      *mInitrdData;
STATIC UINTN                     mInitrdSize;
STATIC EFI_HANDLE                mInitrdHandle;
STATIC EFI_LOAD_FILE2_PROTOCOL   mInitrdLoadFile2;
STATIC VOID                      *mPayloadCopy;
STATIC UINTN                     mPayloadBase = PAYLOAD_BASE;

STATIC
EFI_STATUS
EFIAPI
LinuxLauncherLoadFile2 (
  IN EFI_LOAD_FILE2_PROTOCOL   *This,
  IN EFI_DEVICE_PATH_PROTOCOL  *FilePath,
  IN BOOLEAN                   BootPolicy,
  IN OUT UINTN                 *BufferSize,
  IN VOID                      *Buffer OPTIONAL
  )
{
  if ((This == NULL) || (BufferSize == NULL) || (FilePath == NULL) ||
      !IsDevicePathValid (FilePath, 0)) {
    return EFI_INVALID_PARAMETER;
  }

  if (BootPolicy) {
    return EFI_UNSUPPORTED;
  }

  if (mInitrdSize == 0) {
    return EFI_NOT_FOUND;
  }

  if ((Buffer == NULL) || (*BufferSize < mInitrdSize)) {
    *BufferSize = mInitrdSize;
    return EFI_BUFFER_TOO_SMALL;
  }

  CopyMem (Buffer, mInitrdData, mInitrdSize);
  *BufferSize = mInitrdSize;

  return EFI_SUCCESS;
}

STATIC
EFI_STATUS
LinuxLauncherInstallInitrd (
  VOID
  )
{
  if (mInitrdSize == 0) {
    return EFI_NOT_FOUND;
  }

  mInitrdLoadFile2.LoadFile = LinuxLauncherLoadFile2;
  return gBS->InstallMultipleProtocolInterfaces (
                &mInitrdHandle,
                &gEfiLoadFile2ProtocolGuid,
                &mInitrdLoadFile2,
                &gEfiDevicePathProtocolGuid,
                &mRamdiskDevicePath,
                NULL
                );
}

STATIC
EFI_STATUS
LinuxLauncherParsePayload (
  OUT XNUP_PAYLOAD  *Payload
  )
{
  XNUP_HEADER     *Header;
  XNUP_ENTRY      *Entry;
  CONST UINT8     *EntryPtr;
  CONST UINT8     *PayloadEnd;
  CONST UINT8     *Data;

  ZeroMem (Payload, sizeof (*Payload));
  Header = (XNUP_HEADER *)(UINTN)mPayloadBase;

  if (Header->Magic != XNUP_MAGIC) {
    return EFI_NOT_FOUND;
  }

  if (Header->Size < sizeof (XNUP_ENTRY)) {
    return EFI_INVALID_PARAMETER;
  }

  if (Header->Size > PAYLOAD_MAX_SIZE - sizeof (XNUP_HEADER)) {
    return EFI_INVALID_PARAMETER;
  }

  EntryPtr   = (CONST UINT8 *)(Header + 1);
  PayloadEnd = EntryPtr + Header->Size;

  while (EntryPtr + sizeof (XNUP_ENTRY) <= PayloadEnd) {
    Entry = (XNUP_ENTRY *)EntryPtr;
    if (Entry->Name[0] == '\0') {
      break;
    }

    Data = EntryPtr + sizeof (XNUP_ENTRY);
    if ((UINT64)Entry->Size > (UINT64)(PayloadEnd - Data)) {
      return EFI_INVALID_PARAMETER;
    }

    if (AsciiStrnCmp (Entry->Name, "Image", sizeof (Entry->Name)) == 0) {
      Payload->Image     = Data;
      Payload->ImageSize = Entry->Size;
    } else if (AsciiStrnCmp (Entry->Name, "dtb", sizeof (Entry->Name)) == 0) {
      Payload->Dtb     = Data;
      Payload->DtbSize = Entry->Size;
    } else if (AsciiStrnCmp (Entry->Name, "ramdisk", sizeof (Entry->Name)) == 0) {
      Payload->Ramdisk     = Data;
      Payload->RamdiskSize = Entry->Size;
    } else if (AsciiStrnCmp (Entry->Name, "cmdline", sizeof (Entry->Name)) == 0) {
      Payload->Cmdline = (CONST CHAR8 *)Data;
    }

    EntryPtr = Data + ALIGN_VALUE ((UINTN)Entry->Size, 16);
    if (EntryPtr < Data) {
      return EFI_INVALID_PARAMETER;
    }
  }

  if (Payload->Image == NULL) {
    return EFI_NOT_FOUND;
  }

  return EFI_SUCCESS;
}

STATIC
VOID
LinuxLauncherReadyToBoot (
  IN EFI_EVENT  Event,
  IN VOID       *Context
  )
{
  EFI_STATUS      Status;
  XNUP_PAYLOAD    Payload;
  CHAR16          Cmdline[CMDLINE_MAX_SIZE];
  EFI_HANDLE      ImageHandle;
  UINTN           ExitDataSize;
  CHAR16          *ExitData;

  Status = LinuxLauncherParsePayload (&Payload);
  if (EFI_ERROR (Status)) {
    Print (L"LinuxLauncher: no payload at 0x%x (%r)\n", (UINT32)mPayloadBase, Status);
    return;
  }

  Print (
    L"LinuxLauncher: Image 0x%x, DTB 0x%x, ramdisk 0x%x\n",
    (UINT32)Payload.ImageSize,
    (UINT32)Payload.DtbSize,
    (UINT32)Payload.RamdiskSize
    );

  if (Payload.Dtb != NULL) {
    Status = gBS->InstallConfigurationTable (&gFdtTableGuid, (VOID *)Payload.Dtb);
    Print (L"LinuxLauncher: InstallConfigurationTable(FDT) = %r\n", Status);
  }

  if (Payload.Ramdisk != NULL) {
    mInitrdData = (VOID *)Payload.Ramdisk;
    mInitrdSize = Payload.RamdiskSize;
    Status      = LinuxLauncherInstallInitrd ();
    Print (L"LinuxLauncher: LoadFile2(initrd) = %r\n", Status);
  }

  if (Payload.Cmdline != NULL) {
    AsciiStrToUnicodeStrS (Payload.Cmdline, Cmdline, ARRAY_SIZE (Cmdline));
  } else {
    StrCpyS (Cmdline, ARRAY_SIZE (Cmdline), L"console=tty0 loglevel=7 ignore_loglevel");
  }

  ImageHandle = NULL;
  ExitData    = NULL;
  Status      = gBS->LoadImage (
                         FALSE,
                         gImageHandle,
                         NULL,
                         (VOID *)Payload.Image,
                         Payload.ImageSize,
                         &ImageHandle
                         );
  if (EFI_ERROR (Status)) {
    Print (L"LinuxLauncher: LoadImage = %r\n", Status);
    return;
  }

  Print (L"LinuxLauncher: starting Linux (%s)\n", Cmdline);
  Status = gBS->StartImage (
                  ImageHandle,
                  &ExitDataSize,
                  &ExitData
                  );
  Print (L"LinuxLauncher: StartImage = %r\n", Status);
  if (ExitData != NULL) {
    gBS->FreePool (ExitData);
  }
}

EFI_STATUS
EFIAPI
LinuxLauncherEntryPoint (
  IN EFI_HANDLE        ImageHandle,
  IN EFI_SYSTEM_TABLE  *SystemTable
  )
{
  EFI_STATUS             Status;
  EFI_EVENT              Event;
  XNUP_HEADER            *Header;
  EFI_PHYSICAL_ADDRESS   PayloadAddress;
  UINTN                  PayloadPages;
  UINTN                  PayloadSize;

  Header = (XNUP_HEADER *)(UINTN)PAYLOAD_BASE;
  if ((Header->Magic == XNUP_MAGIC) &&
      (Header->Size <= PAYLOAD_MAX_SIZE - sizeof (XNUP_HEADER))) {
    PayloadSize    = sizeof (XNUP_HEADER) + Header->Size;
    PayloadPages   = EFI_SIZE_TO_PAGES (PayloadSize);
    PayloadAddress = PAYLOAD_BASE;
    Status         = gBS->AllocatePages (
                            AllocateAddress,
                            EfiRuntimeServicesData,
                            PayloadPages,
                            &PayloadAddress
                            );
    if (EFI_ERROR (Status)) {
      Status = gBS->AllocatePool (
                      EfiLoaderData,
                      PayloadSize,
                      &mPayloadCopy
                      );
      if (!EFI_ERROR (Status)) {
        CopyMem (mPayloadCopy, (VOID *)(UINTN)PAYLOAD_BASE, PayloadSize);
        mPayloadBase = (UINTN)mPayloadCopy;
      }
    }

    Print (L"LinuxLauncher: payload 0x%x (%u pages) at 0x%x = %r\n",
           (UINT32)PayloadSize, (UINT32)PayloadPages, (UINT32)mPayloadBase, Status);
  }

  Status = gBS->CreateEventEx (
                  EVT_NOTIFY_SIGNAL,
                  TPL_CALLBACK,
                  LinuxLauncherReadyToBoot,
                  NULL,
                  &gEfiEventReadyToBootGuid,
                  &Event
                  );
  if (EFI_ERROR (Status)) {
    Print (L"LinuxLauncher: CreateEventEx = %r\n", Status);
    return Status;
  }

  Print (L"LinuxLauncher: armed for ReadyToBoot\n");
  return EFI_SUCCESS;
}
