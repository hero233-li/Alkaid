我看了这个页面，后端要适配的核心是两类接口：

```txt
1. 查询客户卡片
POST /api/product-data/tools/cards/search

2. 对某张卡执行动作
POST /api/product-data/tools/cards/{cardNo}/actions/{action}
```

前端动作一共有 5 个：

```ts
deposit              存钱
withdraw             取现
transfer             转账
card-pin-reset        卡密重置
login-password-reset  登录密码重置
```

这些是前端配置里写死的。查询接口和操作接口也已经在 `api/cardStatus.ts` 里定好了。([GitHub][1]) 前端最终需要的表格字段是 `environment、customerNo、certificateNo、cardNo、balance、status`，操作成功后需要返回 `actionResult.card` 和 `actionResult.message`，如果是密码重置还可以返回 `actionResult.password`。([GitHub][2]) ([GitHub][3])

不过先提醒你一个坑：你这个页面现在轮询写的是：

```ts
GET /api/jobs/{id}
```

而且前端会 `unwrap()`，也就是期待后端返回：

```json
{
  "ok": true,
  "data": {
    "id": "...",
    "status": "success",
    "progress": 100,
    "result": {}
  }
}
```

但你 GitHub 当前后端通用 `job_detail` 返回的是原始 `serialize_job(job)`，没有 `ok/data` 包装。([GitHub][4]) 所以我建议这页单独加一个 wrapper 查询接口，然后前端把轮询地址改成：

```ts
/product-data/tools/cards/jobs/${id}
```

不要直接用全局 `/api/jobs/{id}`，否则容易影响旧页面。

---

## 一、后端新增 view

新增文件：

```txt
apps/backend/core/card_status_views.py
```

直接放这个：

```py
import json
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from jobs.models import Job, JobLog
from jobs.serializers import serialize_job


def api_ok(data=None, message="ok"):
    return JsonResponse({
        "ok": True,
        "data": data,
        "message": message,
    })


def api_fail(message, status=400):
    return JsonResponse({
        "ok": False,
        "data": None,
        "message": message,
    }, status=status)


def serialize_card_job_submission(job):
    return {
        "id": str(job.id),
        "status": job.status,
        "progress": job.progress,
    }


def serialize_card_job_detail(job):
    data = serialize_job(job)

    return {
        "id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "currentStep": data.get("current_step"),
        "result": data.get("result") or {},
        "errorMessage": data.get("error") or "",
    }


def create_card_job(name, biz_payload):
    job = Job.objects.create(
        name=name,
        payload={
            "workflow": "card_status",
            "biz_payload": json.dumps(biz_payload, ensure_ascii=False),
        },
        stage=Job.STAGE_SUBMITTED,
        progress=5,
        current_step=0,
        total_steps=3,
    )

    JobLog.objects.create(
        job=job,
        message=f"{name}任务已创建，等待 worker 执行",
    )

    return job


@csrf_exempt
@require_http_methods(["POST"])
def card_search(request):
    try:
        values = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return api_fail("请求 JSON 解析失败", status=400)

    job = create_card_job(
        name="卡片查询",
        biz_payload={
            "action": "search",
            "values": values,
        },
    )

    return api_ok(
        serialize_card_job_submission(job),
        "卡片查询任务已提交",
    )


@csrf_exempt
@require_http_methods(["POST"])
def card_action(request, card_no, action):
    try:
        values = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return api_fail("请求 JSON 解析失败", status=400)

    job = create_card_job(
        name=f"卡片操作-{action}",
        biz_payload={
            "action": action,
            "cardNo": str(card_no),
            "values": values,
        },
    )

    return api_ok(
        serialize_card_job_submission(job),
        "卡片操作任务已提交",
    )


@require_http_methods(["GET"])
def card_job_detail(request, job_id):
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return api_fail("Job 不存在", status=404)

    return api_ok(
        serialize_card_job_detail(job),
        "获取卡处理 Job 成功",
    )
```

---

## 二、urls.py 加路由

打开：

```txt
apps/backend/automation_backend/urls.py
```

加导入：

```py
from core import card_status_views
```

加路由：

```py
path(
    "api/product-data/tools/cards/search",
    card_status_views.card_search,
),
path(
    "api/product-data/tools/cards/<str:card_no>/actions/<str:action>",
    card_status_views.card_action,
),
path(
    "api/product-data/tools/cards/jobs/<uuid:job_id>",
    card_status_views.card_job_detail,
),
```

注意：这个新页面的前端 `cardStatusClient` 的 `baseURL` 是 `/api`，所以后端真实地址要从 `/api/product-data/...` 开始。([GitHub][5])

---

## 三、前端轮询地址要小改一下

你现在 `api/cardStatus.ts` 里面是：

```ts
cardStatusClient.get(`/jobs/${id}`, config)
```

建议改成：

```ts
cardStatusClient.get(`/product-data/tools/cards/jobs/${id}`, config)
```

完整就是：

```ts
export async function pollCardJob(id: string, onProgress: (job: CardJob) => void) {
  while (true) {
    const job = unwrap(
      (await cardStatusClient.get<CardApiResponse<CardJob>>(
        `/product-data/tools/cards/jobs/${id}`,
        config,
      )).data,
      '获取卡处理 Job 失败',
    );

    onProgress(job);

    if (job.status === 'success') return job;

    if (terminal.has(job.status)) {
      throw new Error(job.errorMessage || `Job ${job.status}`);
    }

    await new Promise((resolve) => window.setTimeout(resolve, 400));
  }
}
```

还有类型里 `id` 建议从 `number` 改成 `string`，因为你后端 `Job.id` 是 UUID。当前后端模型里 Job 主键就是 `UUIDField`。([GitHub][6])

---

## 四、新增 workflow

新增目录：

```txt
apps/backend/workflows/card_status/
  __init__.py
  workflow.py
```

`__init__.py`：

```py
from .workflow import run_card_status_workflow

__all__ = ["run_card_status_workflow"]
```

`workflow.py`：

```py
import hashlib
import random
from decimal import Decimal, ROUND_HALF_UP

from workflows.common import WorkflowStep, parse_payload, run_steps


CARD_ACTION_LABELS = {
    "deposit": "存钱",
    "withdraw": "取现",
    "transfer": "转账",
    "card-pin-reset": "卡密重置",
    "login-password-reset": "登录密码重置",
}


def run_card_status_workflow(job):
    workflow = CardStatusWorkflow(job)

    return run_steps(
        job=job,
        workflow=workflow,
        start_message="卡片状态处理流程开始",
        result_message="[写入执行结果] 卡片状态处理结果已保存",
        complete_message="卡片状态处理完成",
    )


class CardStatusWorkflow:
    def __init__(self, job):
        self.job = job
        self.payload = parse_payload(job.payload.get("biz_payload"))
        self.action = self.payload.get("action") or "search"
        self.card_no = self.payload.get("cardNo") or ""
        self.values = self.payload.get("values") or {}
        self.context = {}

    def build_steps(self):
        if self.action == "search":
            return [
                WorkflowStep("校验查询参数", self.validate_search),
                WorkflowStep("查询客户卡片", self.search_cards),
            ]

        return [
            WorkflowStep("校验操作参数", self.validate_action),
            WorkflowStep("执行卡片操作", self.execute_action),
        ]

    def validate_search(self):
        required = ["environment", "customerNo"]
        missing = [field for field in required if not self.values.get(field)]

        if missing:
            raise ValueError(f"查询参数缺失：{', '.join(missing)}")

        return (
            f"环境：{self.values.get('environment')}；"
            f"客户号：{self.values.get('customerNo')}"
        )

    def search_cards(self):
        environment = self.values.get("environment")
        customer_no = self.values.get("customerNo")
        certificate_no = self._mock_certificate_no(customer_no)

        cards = []

        for index in range(1, 4):
            card_no = self._mock_card_no(customer_no, index)
            cards.append({
                "environment": environment,
                "customerNo": customer_no,
                "certificateNo": certificate_no,
                "cardNo": card_no,
                "balance": float(self._mock_balance(card_no)),
                "status": "正常",
            })

        self.context["cards"] = cards

        return f"查询到 {len(cards)} 张卡片"

    def validate_action(self):
        supported = set(CARD_ACTION_LABELS.keys())

        if self.action not in supported:
            raise ValueError(f"不支持的卡片操作：{self.action}")

        required = [
            "environment",
            "customerNo",
            "certificateNo",
            "cardNo",
            "tellerNo",
        ]

        if self.action in ("deposit", "withdraw", "transfer"):
            required.append("amount")

        if self.action == "transfer":
            required.append("targetCard")

        missing = [field for field in required if self.values.get(field) in (None, "")]

        if missing:
            raise ValueError(f"操作参数缺失：{', '.join(missing)}")

        return f"操作类型：{CARD_ACTION_LABELS.get(self.action)}；卡号：{self.card_no}"

    def execute_action(self):
        card = self._build_card_from_values()
        amount = self._money(self.values.get("amount") or 0)

        password = None

        if self.action == "deposit":
            card["balance"] = float(self._money(card["balance"]) + amount)
            message = f"存钱成功，金额 {amount}"

        elif self.action == "withdraw":
            current_balance = self._money(card["balance"])

            if current_balance < amount:
                raise ValueError("卡余额不足，无法取现")

            card["balance"] = float(current_balance - amount)
            message = f"取现成功，金额 {amount}"

        elif self.action == "transfer":
            current_balance = self._money(card["balance"])
            target_card = self.values.get("targetCard")

            if current_balance < amount:
                raise ValueError("卡余额不足，无法转账")

            if target_card == card["cardNo"]:
                raise ValueError("转入卡号不能和当前卡号相同")

            card["balance"] = float(current_balance - amount)
            message = f"转账成功，金额 {amount}，转入卡号 {target_card}"

        elif self.action == "card-pin-reset":
            password = self._mock_password("card-pin", card["cardNo"])
            message = "卡密重置成功"

        elif self.action == "login-password-reset":
            password = self._mock_password("login-password", card["cardNo"])
            message = "登录密码重置成功"

        else:
            raise ValueError(f"不支持的卡片操作：{self.action}")

        self.context["actionResult"] = {
            "card": card,
            "message": message,
        }

        if password:
            self.context["actionResult"]["password"] = password

        return message

    def build_result(self):
        if self.action == "search":
            return {
                "cards": self.context.get("cards") or [],
            }

        return {
            "actionResult": self.context.get("actionResult") or {},
        }

    def _build_card_from_values(self):
        card_no = self.values.get("cardNo") or self.card_no
        customer_no = self.values.get("customerNo")

        return {
            "environment": self.values.get("environment"),
            "customerNo": customer_no,
            "certificateNo": self.values.get("certificateNo"),
            "cardNo": card_no,
            "balance": float(self._mock_balance(card_no)),
            "status": "正常",
        }

    def _mock_card_no(self, customer_no, index):
        seed = self._hash_int(f"{customer_no}|card|{index}")
        body = f"622202{seed % 10 ** 12:012d}"
        return body + self._luhn_check_digit(body)

    def _mock_certificate_no(self, customer_no):
        seed = self._hash_int(f"{customer_no}|certificate")
        area = "110101"
        birthday = "19900101"
        seq = seed % 999

        if seq == 0:
            seq = 1

        body17 = f"{area}{birthday}{seq:03d}"
        return body17 + self._id_check_digit(body17)

    def _mock_balance(self, card_no):
        seed = self._hash_int(f"{card_no}|balance")
        amount = Decimal(seed % 1000000) / Decimal("100")
        return self._money(amount)

    def _mock_password(self, namespace, card_no):
        seed = self._hash_int(f"{namespace}|{card_no}|{self.values.get('tellerNo')}")
        return f"{seed % 1000000:06d}"

    def _money(self, value):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _hash_int(self, text):
        return int(hashlib.sha256(str(text).encode("utf-8")).hexdigest(), 16)

    def _luhn_check_digit(self, body):
        total = 0

        for index, char in enumerate(body[::-1]):
            num = int(char)

            if index % 2 == 0:
                num *= 2
                if num > 9:
                    num -= 9

            total += num

        return str((10 - total % 10) % 10)

    def _id_check_digit(self, body17):
        weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
        codes = "10X98765432"
        total = sum(int(num) * weight for num, weight in zip(body17, weights))
        return codes[total % 11]
```

这个版本是 mock 版，能先跑通页面。后面你如果要接真实核心系统，就把这些方法替换掉：

```py
search_cards()
execute_action()
```

具体就是：

```txt
search_cards      -> 调真实卡查询接口
deposit           -> 调真实存钱接口
withdraw          -> 调真实取现接口
transfer          -> 调真实转账接口
card-pin-reset    -> 调真实卡密重置接口
login-password-reset -> 调真实登录密码重置接口
```

但返回给前端的结构别变。

---

## 五、注册 workflow

打开：

```txt
apps/backend/workflows/registry.py
```

当前注册表只有 `product_apply、search_form_2、reset_password`。([GitHub][7]) 你加上：

```py
from workflows.card_status import run_card_status_workflow
```

然后：

```py
WORKFLOW_RUNNERS = {
    "product_apply": run_product_apply_workflow,
    "search_form_2": run_search_form_2_workflow,
    "reset_password": run_reset_password_workflow,
    "card_status": run_card_status_workflow,
}
```

---

## 六、前端类型顺手修一下

你现在 `types.ts` 里有这个问题：

```ts
export interface CardApiResponse{ok:boolean;data:T;message?:string}
```

这里 `T` 没声明泛型，应该改成：

```ts
export interface CardApiResponse<T = unknown> {
  ok: boolean;
  data: T;
  message?: string;
}
```

另外 Job id 改成 string：

```ts
export interface CardJob {
  id: string;
  status: CardJobStatus;
  progress: number;
  currentStep?: string;
  result: Record<string, unknown>;
  errorMessage?: string;
}

export interface CardActivity {
  jobId?: string;
  label: string;
  status: CardJobStatus;
  progress: number;
  currentStep?: string;
}
```

---

你现在最小落地顺序：

```txt
1. 新增 core/card_status_views.py
2. urls.py 加 3 条路由
3. 新增 workflows/card_status
4. registry.py 注册 card_status
5. 前端 pollCardJob 改成 /product-data/tools/cards/jobs/${id}
6. types.ts 把 CardApiResponse<T> 和 id:string 修一下
```

跑通后，这个页面的链路就是：

```txt
查询客户号
  -> 后端返回 result.cards
  -> 表格展示卡片
  -> 勾选卡片
  -> 点击存钱/取现/转账/重置
  -> 后端返回 result.actionResult
  -> 前端更新这一张卡
  -> 如果返回 password，就弹新密码弹窗
```

[1]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/web/src/pages/CardStatusProcessingPage/api/cardStatus.ts "raw.githubusercontent.com"
[2]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/web/src/pages/CardStatusProcessingPage/hooks/useCardStatusProcessing.ts "raw.githubusercontent.com"
[3]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/web/src/pages/CardStatusProcessingPage/types.ts "raw.githubusercontent.com"
[4]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/backend/jobs/views.py "raw.githubusercontent.com"
[5]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/web/src/pages/CardStatusProcessingPage/api/client.ts "raw.githubusercontent.com"
[6]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/backend/jobs/models.py "raw.githubusercontent.com"
[7]: https://raw.githubusercontent.com/hero233-li/yuheng/main/apps/backend/workflows/registry.py "raw.githubusercontent.com"
