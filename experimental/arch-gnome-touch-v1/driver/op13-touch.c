/* SPDX-License-Identifier: BSD-2-Clause
 * Linux binding for the already validated OP13 GPIO/S3910 protocol.
 * Requires explicit firmware preparation and a disabled kernel SPI node.
 * No supply, reset, firmware-download, storage or flash operations here.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/uinput.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/resource.h>
#include <time.h>
#include <unistd.h>
#include "op13_bitbang.h"
#include "touch-events.h"
_Static_assert(T_ABS==EV_ABS && T_BTN_TOUCH==BTN_TOUCH && T_SLOT==ABS_MT_SLOT &&
 T_TRACKING==ABS_MT_TRACKING_ID && T_MT_X==ABS_MT_POSITION_X,"Linux input ABI");
static volatile uint32_t *spi, *panel;
static struct op13_bitbang bus;
static struct s3910 controller;
static struct touch_events events;
static volatile sig_atomic_t stopped;
static int ui=-1;
static unsigned reported;
static uint64_t ns(void)
{struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return (uint64_t)t.tv_sec*1000000000+t.tv_nsec;}
static int allowed(uint32_t off)
{unsigned p=off/4096,r=off%4096;return p>=48&&p<=51&&(r==0||r==4);}
static int rd(void *cookie,uint32_t off,uint32_t *v)
{
 (void)cookie;if(!allowed(off)||!v)return -1;
 __asm__ volatile("dsb sy":::"memory");*v=spi[(off-48*4096)/4];
 __asm__ volatile("dsb sy":::"memory");return 0;
}
static int wr(void *cookie,uint32_t off,uint32_t v)
{
 (void)cookie;if(!allowed(off)||off==48*4096+4)return -1;
 __asm__ volatile("dsb sy":::"memory");spi[(off-48*4096)/4]=v;
 __asm__ volatile("dsb sy":::"memory");return 0;
}
static int delay_us(void *cookie,unsigned us)
{(void)cookie;if(us>1000000)return -1;uint64_t until=ns()+(uint64_t)us*1000;while(ns()<until){}return 0;}
static int read_spi(void *cookie,uint8_t *data,size_t n)
{(void)cookie;return op13_bitbang_transfer(&bus,NULL,data,n);}
static int write_spi(void *cookie,const uint8_t *data,size_t n)
{(void)cookie;return op13_bitbang_transfer(&bus,data,NULL,n);}
static int irq(void *cookie)
{(void)cookie;__asm__ volatile("dsb sy":::"memory");return !(panel[(4096+4)/4]&1);}
static void sleep_ms(void *cookie,unsigned ms)
{(void)cookie;struct timespec t={ms/1000,(long)(ms%1000)*1000000};while(nanosleep(&t,&t)&&errno==EINTR&&!stopped){} }
static int emit(void *cookie,unsigned type,unsigned code,int value)
{
 (void)cookie;struct input_event e={0};e.type=type;e.code=code;e.value=value;
 return write(ui,&e,sizeof(e))==(ssize_t)sizeof(e)?0:-1;
}
static void post(void *cookie,unsigned type,unsigned slot,uint32_t x,uint32_t y)
{
 (void)cookie;touch_post(&events,type,slot,x,y);
 if(reported++<32)fprintf(stderr,"TOUCH event=%u slot=%u x=%u y=%u\n",type,slot,x,y);
}
static int abs_axis(unsigned code,int minimum,int maximum)
{
 struct uinput_abs_setup a={0};a.code=code;a.absinfo.minimum=minimum;a.absinfo.maximum=maximum;
 if(ioctl(ui,UI_SET_ABSBIT,code)<0 || ioctl(ui,UI_ABS_SETUP,&a)<0)return -1;
 return 0;
}
static int setup_input(void)
{
 ui=open("/dev/uinput",O_WRONLY|O_NONBLOCK);
 if(ui<0){perror("open /dev/uinput");return -1;}
 if(ioctl(ui,UI_SET_EVBIT,EV_KEY)<0||ioctl(ui,UI_SET_KEYBIT,BTN_TOUCH)<0||
    ioctl(ui,UI_SET_EVBIT,EV_ABS)<0||ioctl(ui,UI_SET_PROPBIT,INPUT_PROP_DIRECT)<0||
    abs_axis(ABS_X,0,65535)||abs_axis(ABS_Y,0,65535)||
    abs_axis(ABS_MT_SLOT,0,9)||abs_axis(ABS_MT_TRACKING_ID,0,65535)||
    abs_axis(ABS_MT_POSITION_X,0,65535)||abs_axis(ABS_MT_POSITION_Y,0,65535))return -1;
 struct uinput_setup u={0};u.id.bustype=BUS_VIRTUAL;u.id.vendor=0x06cb;u.id.product=0x3910;
 strcpy(u.name,"OnePlus13 S3910 RAM touch");
 if(ioctl(ui,UI_DEV_SETUP,&u)<0||ioctl(ui,UI_DEV_CREATE)<0)return -1;
 events.emit=emit;
 return 0;
}
static int read_small(const char *path,char *b,size_t capacity)
{int fd=open(path,O_RDONLY);if(fd<0)return -1;ssize_t n=read(fd,b,capacity-1);close(fd);if(n<0)return -1;b[n]=0;return 0;}
static void stop(int signal){(void)signal;stopped=1;}
int main(int argc,char **argv)
{
 setvbuf(stderr,NULL,_IONBF,0);
 char commandline[8192],status[64];
 if(argc!=2||strcmp(argv[1],"--firmware-lease")||read_small("/proc/cmdline",commandline,sizeof(commandline))){
  fprintf(stderr,"REFUSED: explicit firmware lease required\n");return 2;
 }
 int opted=0;char *save=NULL;
 for(char *t=strtok_r(commandline," \n",&save);t;t=strtok_r(NULL," \n",&save))if(!strcmp(t,"op13_touch=1"))opted=1;
 if(!opted||read_small("/proc/device-tree/soc@0/geniqup@ac0000/spi@a90000/status",status,sizeof(status))||strcmp(status,"disabled")){
  fprintf(stderr,"REFUSED: opt-in or disabled kernel SPI controller missing\n");return 2;
 }
 int mem=open("/dev/mem",O_RDWR|O_SYNC);
 if(mem<0){perror("open /dev/mem");return 3;}
 spi=mmap(NULL,0x4000,PROT_READ|PROT_WRITE,MAP_SHARED,mem,0x0f130000);
 panel=mmap(NULL,0x2000,PROT_READ,MAP_SHARED,mem,0x0f1a1000);close(mem);
 if(spi==MAP_FAILED||panel==MAP_FAILED){perror("map bounded GPIO pages");return 3;}
 static const uint32_t expected[4]={0x80,0x240,0x280,0x240};
 for(unsigned i=0;i<4;i++){
  uint32_t config=spi[i*1024];
  fprintf(stderr,"GPIO%u config=%#x expected=%#x\n",48+i,config,expected[i]);
  if((config&0x3ff)!=expected[i]||(config&0x1800)){
   fprintf(stderr,"REFUSED: SPI GPIO lease changed; no MMIO writes\n");return 4;
  }
 }
 if((panel[0]&0x3ff)!=0x2c0||(panel[1024]&0x3ff)!=0xc0||!(panel[1]&2)){
  fprintf(stderr,"REFUSED: reset/IRQ lease changed; no MMIO writes\n");return 4;
 }
 bus.io=(struct op13_bitbang_io){NULL,rd,wr,delay_us};bus.ready=1;
 signal(SIGTERM,stop);signal(SIGINT,stop);setpriority(PRIO_PROCESS,0,-5);
 struct s3910_io io={NULL,read_spi,write_spi,irq,sleep_ms,post};
 int error=s3910_probe(&controller,&io);
 fprintf(stderr,"S3910 probe=%d header=%02x %02x %02x %02x mode=%u\n",error,
  controller.startup_header[0],controller.startup_header[1],controller.startup_header[2],controller.startup_header[3],controller.identification[1]);
 if(error)return 5;
 error=s3910_enable_lbp(&controller);
 fprintf(stderr,"S3910 LBP=%d bounds=%ux%u slots=%u command=%#x status=%#x\n",error,
  controller.max_x,controller.max_y,controller.max_objects,controller.last_command,controller.last_status);
 if(error)return 6;
 if(setup_input()){perror("uinput setup");return 7;}
 fprintf(stderr,"TOUCH READY: S3910 polling into Linux multitouch input\n");
 while(!stopped){
  error=s3910_poll(&controller);touch_sync(&events);
  if(error||events.failed)break;
  sleep_ms(NULL,4);
 }
 s3910_release_all(&controller);touch_sync(&events);
 ioctl(ui,UI_DEV_DESTROY);close(ui);
 fprintf(stderr,"TOUCH STOP: error=%d input-failed=%d frames=%u bad=%u events=%u\n",error,events.failed,controller.frames,controller.bad_frames,reported);
 return error||events.failed?8:0;
}
