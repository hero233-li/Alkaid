import type{CardAction}from'../types';
export const cardStatusConfig={
  environments:['环境1','环境2','环境3'],
  defaultTellerNo:'310310',
  actions:[
    {value:'deposit',label:'存钱'},
    {value:'withdraw',label:'取现'},
    {value:'transfer',label:'转账'},
    {value:'card-pin-reset',label:'卡密重置'},
    {value:'login-password-reset',label:'登录密码重置'},
  ]as Array<{value:CardAction;label:string}>,
};
export const cardActionLabel=(action:CardAction)=>cardStatusConfig.actions.find(item=>item.value===action)?.label??action;
