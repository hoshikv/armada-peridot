/* SPDX-License-Identifier: BSD-2-Clause */
#ifndef OP13_LINUX_TOUCH_EVENTS_H
#define OP13_LINUX_TOUCH_EVENTS_H
#include <stdint.h>
#include "s3910.h"
enum { T_SYN=0, T_KEY=1, T_ABS=3, T_BTN_TOUCH=330,
       T_X=0, T_Y=1, T_SLOT=47, T_MT_X=53, T_MT_Y=54, T_TRACKING=57 };
struct touch_events {
 void *cookie;
 int (*emit)(void *,unsigned,unsigned,int);
 unsigned active, next_id, dirty;
 uint32_t x[10], y[10];
 int failed;
};
static void touch_emit(struct touch_events *t,unsigned type,unsigned code,int value)
{ if (!t->failed && t->emit(t->cookie,type,code,value))t->failed=1; }
static void touch_post(void *cookie,unsigned kind,unsigned slot,uint32_t x,uint32_t y)
{
 struct touch_events *t=cookie;
 if(slot>=10 || x>65535 || y>65535 || kind<1 || kind>3){t->failed=1;return;}
 touch_emit(t,T_ABS,T_SLOT,(int)slot);
 if(kind==S3910_UP){touch_emit(t,T_ABS,T_TRACKING,-1);t->active&=~(1u<<slot);}
 else {
  if(!(t->active&(1u<<slot))){touch_emit(t,T_ABS,T_TRACKING,(int)(t->next_id++&65535));}
  t->active|=1u<<slot;t->x[slot]=x;t->y[slot]=y;
  touch_emit(t,T_ABS,T_MT_X,(int)x);touch_emit(t,T_ABS,T_MT_Y,(int)y);
 }
 t->dirty=1;
}
static void touch_sync(struct touch_events *t)
{
 if(!t->dirty)return;
 touch_emit(t,T_KEY,T_BTN_TOUCH,!!t->active);
 if(t->active)for(unsigned i=0;i<10;i++)if(t->active&(1u<<i)){
  touch_emit(t,T_ABS,T_X,(int)t->x[i]);touch_emit(t,T_ABS,T_Y,(int)t->y[i]);break;
 }
 touch_emit(t,T_SYN,0,0);t->dirty=0;
}
#endif
