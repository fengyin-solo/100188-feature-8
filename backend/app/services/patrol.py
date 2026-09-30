"""巡查任务业务规则：状态流转、字段校验与筛选口径都收在这里。

状态只能沿 待派发 -> 巡查中 -> 已提交 单向推进；作废是从待派发/巡查中分出的
终态，作废单进入历史分组，不再参与任何统计。提交结果时必须带回巡查路线与发现
问题数，提交后结果不可再被覆盖。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "patrol"
REQUIRED_FIELDS = ["巡查单号", "巡查路线", "巡查人员"]
# 正向三段：只能按这个顺序依次推进，不允许跳级，也不允许回退。
STATUS_ORDER = ["待派发", "巡查中", "已提交"]
VOID_STATUS = "已作废"
ALL_STATUSES = [*STATUS_ORDER, VOID_STATUS]
NEXT_STATUS = {"待派发": "巡查中", "巡查中": "已提交"}
# 提交结果时必须随单填写的字段。
SUBMIT_FIELDS = ["巡查路线", "发现问题数"]


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
            rows = [row for row in rows if keyword in str(row.get("巡查单号", ""))]
        if status:
            rows = [row for row in rows if self._status(row) == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return [self._normalize(row) for row in rows[start:start + size]], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        entry = store.find(MODULE, entry_id)
        return self._normalize(entry) if entry is not None else None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: str(values.get(field)).strip() for field in REQUIRED_FIELDS})
        if str(values.get("巡查日期") or "").strip():
            entry["巡查日期"] = str(values["巡查日期"]).strip()
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        # 巡查单不作异常处理：作废进历史、不进异常量。
        entry["abnormal"] = False
        rows.append(entry)
        return self._normalize(entry), []

    def run_action(
        self,
        entry_id: int,
        action: str,
        values: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"巡查单 {entry_id} 不存在或已归档"
        values = values or {}
        status = self._status(entry)

        if action == "派发巡查":
            if status == VOID_STATUS:
                return None, "巡查单已作废，不能再派发"
            if status != "待派发":
                return None, f"巡查单当前为「{status}」，不能重复派发"
            entry["status"] = "巡查中"
            entry["pending"] = True
            return self._normalize(entry), "巡查单已派发"

        if action == "提交结果":
            if status == VOID_STATUS:
                return None, "巡查单已作废，不能提交结果"
            if status == "已提交":
                # 已提交的结果不允许被重复提交覆盖。
                return None, "巡查单已提交，结果不能重复提交或覆盖"
            if status != "巡查中":
                return None, "巡查单尚未派发，不能直接提交结果"
            route = str(values.get("巡查路线") or "").strip()
            if not route:
                return None, "提交结果时必须填写巡查路线"
            issue_count, issue_error = self._parse_int(values.get("发现问题数"), "发现问题数")
            if issue_error:
                return None, issue_error
            mileage, mileage_error = self._parse_number(values.get("巡查里程"), "巡查里程")
            if mileage_error:
                return None, mileage_error
            # 先落校验再改单：任一字段不合格都保持巡查中，不产生半成品数据。
            entry["巡查路线"] = route
            entry["发现问题数"] = issue_count
            entry["巡查里程"] = mileage
            duration = str(values.get("巡查时长") or "").strip()
            if duration:
                entry["巡查时长"] = duration
            entry["提交日期"] = date.today().isoformat()
            entry["status"] = "已提交"
            entry["pending"] = False
            return self._normalize(entry), "巡查结果已提交"

        if action == "作废巡查":
            if status == VOID_STATUS:
                return None, "巡查单已作废，无需重复作废"
            if status == "已提交":
                return None, "巡查单已提交，不能作废，已提交结果需留存在台账中"
            reason = str(values.get("作废原因") or values.get("remark") or "").strip()
            if not reason:
                return None, "作废巡查必须填写作废原因"
            entry["status"] = VOID_STATUS
            entry["pending"] = False
            entry["abnormal"] = False
            entry["作废原因"] = reason
            entry["作废日期"] = date.today().isoformat()
            return self._normalize(entry), "巡查单已作废并转入历史"

        return None, f"动作「{action}」不属于巡查任务可执行范围"

    def stats(self) -> dict[str, Any]:
        """统计口径与台账一致：只汇总已提交的巡查单，作废单不计入任何指标。"""
        counts = {status: 0 for status in ALL_STATUSES}
        total_mileage = 0.0
        total_issues = 0
        submitted_rows: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            status = self._status(row)
            counts[status] = counts.get(status, 0) + 1
            if status == "已提交":
                total_mileage += self._to_number(row.get("巡查里程"))
                total_issues += self._to_int(row.get("发现问题数"))
                submitted_rows.append(row)
        return {
            "counts": counts,
            "total_mileage": round(total_mileage, 2),
            "total_issues": total_issues,
            "submitted_total": len(submitted_rows),
        }

    @staticmethod
    def _status(entry: dict[str, Any]) -> str:
        """统一读取状态，兼容存量数据里状态写在「巡查状态」字段的情况。"""
        status = str(entry.get("status") or "").strip()
        return status if status in ALL_STATUSES else "待派发"

    def _normalize(self, entry: dict[str, Any]) -> dict[str, Any]:
        """让列表、详情与概览读到同一份状态，字段缺失时补齐展示口径。"""
        status = self._status(entry)
        entry["status"] = status
        entry["巡查状态"] = status
        entry.setdefault("pending", status != "已提交" and status != VOID_STATUS)
        entry.setdefault("abnormal", False)
        if status == "已提交":
            entry.setdefault("发现问题数", 0)
            entry.setdefault("巡查里程", 0)
        return entry

    @staticmethod
    def _parse_int(raw: Any, label: str) -> tuple[int | None, str]:
        text = str(raw if raw is not None else "").strip()
        if not text:
            return None, f"提交结果时必须填写{label}"
        try:
            value = int(float(text))
        except ValueError:
            return None, f"{label}必须是非负整数"
        if value < 0:
            return None, f"{label}不能为负数"
        return value, ""

    @staticmethod
    def _parse_number(raw: Any, label: str) -> tuple[float, str]:
        text = str(raw if raw is not None else "").strip()
        if not text:
            return 0.0, ""
        try:
            value = float(text)
        except ValueError:
            return 0.0, f"{label}必须是数字"
        if value < 0:
            return 0.0, f"{label}不能为负数"
        return value, ""

    @staticmethod
    def _to_int(raw: Any) -> int:
        try:
            value = int(float(raw))
        except (TypeError, ValueError):
            return 0
        return max(value, 0)

    @staticmethod
    def _to_number(raw: Any) -> float:
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return 0.0
        return max(value, 0.0)
