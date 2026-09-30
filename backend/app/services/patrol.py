"""巡查任务业务规则：状态流转、字段校验与筛选口径都收在这里。

状态只允许沿 待派发 → 巡查中 → 已提交 三段依次推进，不允许跳级，也不允许回退；
作废是单独的终态「已作废」，作废单留在历史分组里，不再参与任何统计。
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.store import store

MODULE = "patrol"
REQUIRED_FIELDS = ["巡查单号", "巡查路线", "巡查人员"]
LIST_FIELDS = ["巡查单号", "巡查路线", "巡查人员", "巡查日期", "巡查里程", "发现问题数", "巡查时长", "巡查状态"]

STATUS_PENDING = "待派发"
STATUS_DOING = "巡查中"
STATUS_SUBMITTED = "已提交"
STATUS_VOID = "已作废"
# 正常三段在前，作废终态在最后，前端历史分组也按这个顺序渲染。
STATUS_GROUPS = [STATUS_PENDING, STATUS_DOING, STATUS_SUBMITTED, STATUS_VOID]

ACTION_DISPATCH = "派发巡查"
ACTION_SUBMIT = "提交结果"
ACTION_VOID = "作废巡查"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _parse_issue_count(raw: Any) -> tuple[int | None, str | None]:
    """发现问题数：必填、非负整数。"""
    text = str(raw if raw is not None else "").strip()
    if not text:
        return None, "提交结果时必须填写发现问题数"
    try:
        value = int(text)
    except ValueError:
        return None, "发现问题数必须是不小于 0 的整数"
    if value < 0:
        return None, "发现问题数不能为负数"
    return value, None


def _parse_mileage(raw: Any) -> tuple[float | None, str | None]:
    """巡查里程：参与汇总，要求非负数字；未填时按 0 处理。"""
    text = str(raw if raw is not None else "").strip()
    if not text:
        return 0.0, None
    try:
        value = float(text)
    except ValueError:
        return None, "巡查里程必须是不小于 0 的数字"
    if value < 0:
        return None, "巡查里程不能为负数"
    return value, None


def _serialize_list(entry: dict[str, Any]) -> dict[str, Any]:
    """列表行：统一以 status 作为「巡查状态」，保证列表/详情/概览口径一致。"""
    row: dict[str, Any] = {"id": entry["id"]}
    for field in LIST_FIELDS:
        row[field] = entry["status"] if field == "巡查状态" else entry.get(field)
    return row


def _serialize_detail(entry: dict[str, Any]) -> dict[str, Any]:
    """详情：在列表字段之外补作废原因与操作记录，作废单的历史要留痕。"""
    detail: dict[str, Any] = {"id": entry["id"]}
    for field in LIST_FIELDS:
        detail[field] = entry["status"] if field == "巡查状态" else entry.get(field)
    detail["作废原因"] = entry.get("作废原因")
    detail["操作记录"] = list(entry.get("操作记录", []))
    return detail


class PatrolService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            key = keyword.strip()
            rows = [
                row
                for row in rows
                if key in str(row.get("巡查单号", ""))
                or key in str(row.get("巡查路线", ""))
                or key in str(row.get("巡查人员", ""))
            ]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [_serialize_list(row) for row in rows[start:start + size]], total

    def stats(self) -> dict[str, Any]:
        """汇总卡片：分组计数与里程/问题汇总都以已提交台账为准，作废单不计入。"""
        rows = store.rows(MODULE)
        counts = {status: 0 for status in STATUS_GROUPS}
        mileage_total = 0.0
        issue_total = 0
        for row in rows:
            status = row.get("status")
            if status in counts:
                counts[status] += 1
            if status == STATUS_SUBMITTED:
                mileage_total += float(row.get("巡查里程") or 0)
                issue_total += int(row.get("发现问题数") or 0)
        return {
            "counts": counts,
            "巡查里程合计": round(mileage_total, 2),
            "发现问题数合计": issue_total,
        }

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return _serialize_detail(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in REQUIRED_FIELDS:
            entry[field] = str(values.get(field)).strip()
        patrol_date = str(values.get("巡查日期") or "").strip()
        if patrol_date:
            entry["巡查日期"] = patrol_date
        entry["status"] = STATUS_PENDING
        entry["pending"] = True
        entry["abnormal"] = False
        entry["操作记录"] = [{"动作": "登记巡查单", "时间": _now(), "说明": "巡查单已登记，等待派发"}]
        rows.append(entry)
        return entry, []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
        remark: str | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查单 {entry_id} 不存在或已归档"

        status = str(entry.get("status"))
        if action not in (ACTION_DISPATCH, ACTION_SUBMIT, ACTION_VOID):
            return None, f"动作「{action}」不属于巡查任务可执行范围"
        if status == STATUS_VOID:
            return None, "巡查单已作废，只能在历史分组中查看，不能再执行动作"
        if status == STATUS_SUBMITTED:
            if action == ACTION_SUBMIT:
                return None, "巡查结果已提交，重复提交不会覆盖已有结果"
            if action == ACTION_VOID:
                return None, "巡查结果已提交，不能再作废"
            return None, "巡查结果已提交，状态不能回退"

        if action == ACTION_DISPATCH:
            if status != STATUS_PENDING:
                return None, f"当前状态为「{status}」，只有待派发的巡查单可以派发"
            entry["status"] = STATUS_DOING
            entry["pending"] = True
            entry["abnormal"] = False
            self._log(entry, ACTION_DISPATCH, "巡查单已派发，进入巡查中")
            return entry, "巡查单已派发，进入巡查中"

        if action == ACTION_SUBMIT:
            # 必须先派发：既拦住 待派发→已提交 的跳级，也拦住任何回退。
            if status != STATUS_DOING:
                return None, f"当前状态为「{status}」，需先派发巡查才能提交结果"
            route = str(values.get("巡查路线") or "").strip()
            if not route:
                return None, "提交结果时必须填写巡查路线"
            issue_count, issue_error = _parse_issue_count(values.get("发现问题数"))
            if issue_error:
                return None, issue_error
            mileage, mileage_error = _parse_mileage(values.get("巡查里程"))
            if mileage_error:
                return None, mileage_error
            duration = str(values.get("巡查时长") or "").strip()

            entry["巡查路线"] = route
            entry["巡查里程"] = mileage
            entry["发现问题数"] = issue_count
            if duration:
                entry["巡查时长"] = duration
            entry["status"] = STATUS_SUBMITTED
            entry["pending"] = False
            entry["abnormal"] = False
            self._log(
                entry,
                ACTION_SUBMIT,
                f"路线：{route}；里程：{mileage:g} 公里；发现问题 {issue_count} 个",
            )
            return entry, "巡查结果已提交"

        if action == ACTION_VOID:
            if status not in (STATUS_PENDING, STATUS_DOING):
                return None, f"当前状态为「{status}」，该巡查单不能作废"
            reason = str(remark or values.get("作废原因") or "").strip()
            if not reason:
                return None, "作废巡查必须填写作废原因"
            entry["status"] = STATUS_VOID
            entry["pending"] = False
            entry["abnormal"] = False
            entry["作废原因"] = reason
            self._log(entry, ACTION_VOID, f"作废原因：{reason}")
            return entry, "巡查单已作废，已移入历史分组"

        # 理论上到不了：未知动作已在入口统一拦下。
        return None, f"动作「{action}」不属于巡查任务可执行范围"

    def _log(self, entry: dict[str, Any], action: str, note: str) -> None:
        entry.setdefault("操作记录", []).append({"动作": action, "时间": _now(), "说明": note})
