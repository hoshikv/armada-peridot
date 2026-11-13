#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "touch-events.h"
struct event {unsigned type,code;int value;};
static struct event captured[256];
static unsigned count;
static int emit(void *cookie,unsigned type,unsigned code,int value)
{(void)cookie;assert(count<256);captured[count++]=(struct event){type,code,value};return 0;}
static int find(unsigned type,unsigned code,int value)
{for(unsigned i=0;i<count;i++)if(captured[i].type==type&&captured[i].code==code&&captured[i].value==value)return 1;return 0;}
int main(void)
{
 struct touch_events events={.emit=emit};
 struct s3910 d={.io={.cookie=&events,.event=touch_post},.ready=1,.max_x=1440,.max_y=3168,.max_objects=10,.max_payload=1024};
 uint8_t down[]={1,0,1,0xd0,2,0x30,6}; /* slot 0, center */
 assert(!s3910_touch_payload(&d,down,sizeof(down)));
 assert(!find(T_SYN,0,0));touch_sync(&events);
 assert(events.active==1&&find(T_ABS,T_TRACKING,0));
 assert(find(T_ABS,T_X,32767)&&find(T_ABS,T_Y,32767));
 assert(find(T_KEY,T_BTN_TOUCH,1)&&find(T_SYN,0,0));
 count=0;down[3]=0xa0;down[4]=5;down[5]=0x60;down[6]=12;
 assert(!s3910_touch_payload(&d,down,sizeof(down)));touch_sync(&events);
 assert(find(T_ABS,T_X,65535)&&find(T_ABS,T_Y,65535));
 assert(!find(T_ABS,T_TRACKING,1));
 count=0;uint8_t duplicate[]={2,0,1,0,0,0,0,0,1,0,0,0,0};
 assert(s3910_touch_payload(&d,duplicate,sizeof(duplicate))==S3910_PROTOCOL);
 assert(count==0&&events.active==1); /* Invalid frame emits nothing. */
 s3910_release_all(&d);touch_sync(&events);
 assert(!events.active&&find(T_ABS,T_TRACKING,-1)&&find(T_KEY,T_BTN_TOUCH,0));
 count=0;touch_post(&events,S3910_DOWN,1,0,65535);touch_post(&events,S3910_DOWN,2,65535,0);touch_sync(&events);
 assert(events.active==6&&find(T_ABS,T_X,0));
 count=0;touch_post(&events,S3910_UP,1,0,65535);touch_sync(&events);
 assert(events.active==4&&find(T_ABS,T_X,65535)&&find(T_KEY,T_BTN_TOUCH,1));
 touch_post(&events,S3910_DOWN,10,0,0);assert(events.failed);
 puts("PASS: real S3910 decoder to Linux touch events, scaling, moves, releases, multi-contact and invalid frames");
}
