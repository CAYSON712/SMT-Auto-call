# SMT 场景库

每个 Call Recording 标签对应唯一一个场景。跑场景时用 `--case <用例名或别名>` 调用。

格式约定：
- `## <标签>`：Call Recording 标签名
- `### <用例名> | <别名1> | <别名2>`：用例标识，`--case` 用任何一个都行
- 正文：场景描述（会原样传给 LLM 作为对话目标）

> **Windows 命令行注意**：PowerShell 传中文参数会乱码（如 `订位` 变成 `璁綅`）。
> 命令行调用请用**纯 ASCII 别名**（如 `--case dingwei`），中文名仅在代码内或 Skill 对话中使用。

---

## 自提订单

### pickup | ziti | ziti-dingdan

我要下自提订单，下2份特式水果茶和2份猪扒汤面，姓名是cayson，电话是9023162140

---

## 配送订单

### delivery | peisong | peisong-dingdan

我要下配送订单，下2杯大杯的柠檬茶和2份鲜虾云吞汤面，姓名是cayson，电话是9023162140，地址是中环广场5楼

---

## 订位

### reservation | dingwei | yuding | zuowei

预订明天中午12点的座位、5个人，姓名：cayson，麻烦记下我的电话9023162142，备注需要靠窗

---

## 咨询

### inquiry | zixun

咨询店内有什么菜品和价格如何，先不下单

---

## 第三方订单通知

### 3rd-party | disanfang | third-party

咨询doordash第三方平台外卖订单的配送进度，订单号是123

---

## 投诉反馈

### feedback | tousu | tou-su

投诉店里的牛排太咸了

---

## 信息通知

### notification | tongzhi | xinxi-tongzhi

通知餐厅老板牛肉缺货了，需要尽快补货，请把我的电话9023162140记下来

---

## 转接人工

### transfer | zhuanjie | zhuanjie-rengong

要求转接给餐厅老板

---

## 推销电话

### sales | tuixiao | tuixiao-dianhua

接到一个推销保险的电话，先礼貌听完后明确拒绝他

---

## 无效电话

### invalid | wuxiao | wuxiao-dianhua

模拟一个顾客打错电话，本来想打给别的商家，接通后发现自己打错了，礼貌道歉后结束通话，不咨询任何业务

---

## 语音信箱

### voicemail | yuyin | yuyin-xinxiang

模拟一个顾客想留言，接通后询问是否可以留言，说明来意后简短留言：想咨询明天晚上是否有空位，请店家方便时回电，电话是9023162140，留言完礼貌结束通话
