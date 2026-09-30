<template>
  <section class="page" data-module="patrol">
    <header class="page-head">
      <div>
        <h2>巡查任务管理</h2>
        <p class="page-desc">维护巡查单，围绕巡查单号、巡查路线、巡查人员、巡查日期做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记巡查单</button>
        <button class="btn" type="button" @click="exportRows">导出巡查任务清单</button>
      </div>
    </header>

    <nav class="group-tabs" aria-label="巡查单状态分组">
      <button
        v-for="group in groups"
        :key="group.status"
        type="button"
        class="tab-btn"
        :class="{ active: activeGroup === group.status }"
        @click="switchGroup(group.status)"
      >
        {{ group.label }}
        <em class="tab-count">{{ stats.counts[group.status] ?? 0 }}</em>
      </button>
    </nav>

    <div class="stat-row">
      <article v-for="item in statCards" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键字</span>
        <input v-model="keyword" placeholder="按巡查单号 / 巡查路线 / 巡查人员检索" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ formatCell(row, column) }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">查看详情</button>
            <button
              v-if="row.巡查状态 === '待派发'"
              class="link"
              type="button"
              @click="dispatchRow(row)"
            >
              派发巡查
            </button>
            <button
              v-if="row.巡查状态 === '巡查中'"
              class="link"
              type="button"
              @click="openSubmit(row)"
            >
              提交结果
            </button>
            <button
              v-if="row.巡查状态 === '待派发' || row.巡查状态 === '巡查中'"
              class="link link-danger"
              type="button"
              @click="openVoid(row)"
            >
              作废巡查
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">{{ emptyText }}</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>「{{ activeLabel }}」分组共 {{ total }} 条巡查单</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <!-- 登记巡查单 -->
    <div v-if="dialog === 'create'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3 class="modal-title">登记巡查单</h3>
        <form class="form-grid" @submit.prevent="submitCreate">
          <label class="field">
            <span>巡查单号 <i>*</i></span>
            <input v-model="createForm.巡查单号" placeholder="如 PATR-0005" />
          </label>
          <label class="field">
            <span>巡查日期</span>
            <input v-model="createForm.巡查日期" type="date" />
          </label>
          <label class="field full">
            <span>巡查路线 <i>*</i></span>
            <input v-model="createForm.巡查路线" placeholder="如 河滨大道（一号码头—污水处理厂）" />
          </label>
          <label class="field full">
            <span>巡查人员 <i>*</i></span>
            <input v-model="createForm.巡查人员" placeholder="填写负责巡查的人员姓名" />
          </label>
          <p v-if="dialogError" class="form-error full">{{ dialogError }}</p>
          <div class="modal-actions full">
            <button class="btn" type="button" @click="closeDialog">取消</button>
            <button class="btn primary" type="submit">确认登记</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 提交巡查结果 -->
    <div v-if="dialog === 'submit'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3 class="modal-title">提交巡查结果 · {{ submitTarget?.巡查单号 }}</h3>
        <form class="form-grid" @submit.prevent="submitResult">
          <label class="field full">
            <span>巡查路线 <i>*</i></span>
            <input v-model="submitForm.巡查路线" placeholder="填写实际巡查的路线" />
          </label>
          <label class="field">
            <span>巡查里程（公里）<i>*</i></span>
            <input v-model="submitForm.巡查里程" type="number" min="0" step="0.1" placeholder="如 6.5" />
          </label>
          <label class="field">
            <span>发现问题数 <i>*</i></span>
            <input v-model="submitForm.发现问题数" type="number" min="0" step="1" placeholder="如 3" />
          </label>
          <label class="field full">
            <span>巡查时长</span>
            <input v-model="submitForm.巡查时长" placeholder="如 2.5小时（选填）" />
          </label>
          <p v-if="dialogError" class="form-error full">{{ dialogError }}</p>
          <div class="modal-actions full">
            <button class="btn" type="button" @click="closeDialog">取消</button>
            <button class="btn primary" type="submit">确认提交</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 作废巡查单 -->
    <div v-if="dialog === 'void'" class="modal-mask" @click.self="closeDialog">
      <div class="modal">
        <h3 class="modal-title">作废巡查单 · {{ voidTarget?.巡查单号 }}</h3>
        <form class="form-grid" @submit.prevent="submitVoid">
          <p class="full modal-tip">作废后巡查单将移入「历史」分组，不再计入统计，且无法恢复或继续流转。</p>
          <label class="field full">
            <span>作废原因 <i>*</i></span>
            <textarea v-model="voidReason" rows="3" placeholder="请说明作废原因，该说明会保留在巡查单历史中"></textarea>
          </label>
          <p v-if="dialogError" class="form-error full">{{ dialogError }}</p>
          <div class="modal-actions full">
            <button class="btn" type="button" @click="closeDialog">取消</button>
            <button class="btn danger" type="submit">确认作废</button>
          </div>
        </form>
      </div>
    </div>

    <!-- 巡查单详情 -->
    <div v-if="dialog === 'detail'" class="modal-mask" @click.self="closeDialog">
      <div class="modal modal-wide">
        <h3 class="modal-title">巡查单详情{{ detail ? ` · ${detail.巡查单号}` : '' }}</h3>
        <div v-if="detailLoading" class="modal-tip">详情加载中…</div>
        <template v-else-if="detail">
          <span class="status-badge" :class="badgeClass(detail.巡查状态)">{{ detail.巡查状态 }}</span>
          <dl class="detail-grid">
            <div v-for="column in columns" :key="column">
              <dt>{{ column }}</dt>
              <dd>{{ formatCell(detail, column) }}</dd>
            </div>
            <div class="detail-span">
              <dt>作废原因</dt>
              <dd>{{ detail.作废原因 || '—' }}</dd>
            </div>
          </dl>
          <h4 class="timeline-title">操作记录</h4>
          <ol class="timeline">
            <li v-for="(item, index) in detail.操作记录 ?? []" :key="index">
              <span class="timeline-action">{{ item.动作 }}</span>
              <span class="timeline-time">{{ item.时间 }}</span>
              <p class="timeline-note">{{ item.说明 }}</p>
            </li>
          </ol>
          <p v-if="dialogError" class="form-error">{{ dialogError }}</p>
          <div class="modal-actions">
            <button class="btn primary" type="button" @click="closeDialog">关闭</button>
          </div>
        </template>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type PatrolStatus = '待派发' | '巡查中' | '已提交' | '已作废'
type Row = Record<string, string | number | null>
type DialogMode = '' | 'create' | 'submit' | 'void' | 'detail'

interface HistoryItem {
  动作: string
  时间: string
  说明: string
}

interface DetailRow {
  id?: string | number
  作废原因?: string | null
  操作记录?: HistoryItem[]
  [key: string]: string | number | null | HistoryItem[] | undefined
}

interface StatsPayload {
  counts: Record<PatrolStatus, number>
  巡查里程合计: number
  发现问题数合计: number
}

interface ActionResponse {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/patrol'
const GROUP_STORAGE_KEY = 'patrol:active-group'
const columns = ['巡查单号', '巡查路线', '巡查人员', '巡查日期', '巡查里程', '发现问题数', '巡查时长', '巡查状态']

const groups: { status: PatrolStatus; label: string }[] = [
  { status: '待派发', label: '待派发' },
  { status: '巡查中', label: '巡查中' },
  { status: '已提交', label: '已提交' },
  { status: '已作废', label: '历史（已作废）' },
]

const emptyStats = (): StatsPayload => ({
  counts: { 待派发: 0, 巡查中: 0, 已提交: 0, 已作废: 0 },
  巡查里程合计: 0,
  发现问题数合计: 0,
})

const rows = ref<Row[]>([])
const total = ref(0)
const keyword = ref('')
const errorMessage = ref('')
const stats = ref<StatsPayload>(emptyStats())

const dialog = ref<DialogMode>('')
const dialogError = ref('')
const dialogLoading = ref(false)

const createForm = ref({ 巡查单号: '', 巡查路线: '', 巡查人员: '', 巡查日期: '' })
const submitForm = ref({ 巡查路线: '', 巡查里程: '', 发现问题数: '', 巡查时长: '' })
const submitTarget = ref<Row | null>(null)
const voidTarget = ref<Row | null>(null)
const voidReason = ref('')
const detail = ref<DetailRow | null>(null)
const detailLoading = ref(false)

function loadStoredGroup(): PatrolStatus {
  const stored = window.localStorage.getItem(GROUP_STORAGE_KEY)
  return groups.some((group) => group.status === stored) ? (stored as PatrolStatus) : '待派发'
}

const activeGroup = ref<PatrolStatus>(loadStoredGroup())

const activeLabel = computed(
  () => groups.find((group) => group.status === activeGroup.value)?.label ?? activeGroup.value,
)

const emptyText = computed(() =>
  activeGroup.value === '已作废'
    ? '历史分组暂无作废巡查单'
    : '「' + activeLabel.value + '」分组暂无巡查单',
)

// 卡片全部来自已提交台账的同一批数据，因此与「已提交」分组的行数始终一致。
const statCards = computed(() => [
  { label: '待派发巡查', value: stats.value.counts.待派发 },
  { label: '巡查中任务', value: stats.value.counts.巡查中 },
  { label: '已提交台账（份）', value: stats.value.counts.已提交 },
  { label: '巡查里程合计（公里）', value: stats.value.巡查里程合计 },
  { label: '发现问题数合计（个）', value: stats.value.发现问题数合计 },
])

function formatCell(row: { [key: string]: unknown }, column: string): string | number {
  const value = row[column]
  if (typeof value === 'number') return value
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function badgeClass(status: unknown): string {
  return {
    待派发: 'badge-pending',
    巡查中: 'badge-doing',
    已提交: 'badge-done',
    已作废: 'badge-void',
  }[String(status)] ?? ''
}

function switchGroup(status: PatrolStatus) {
  if (activeGroup.value === status) return
  activeGroup.value = status
  window.localStorage.setItem(GROUP_STORAGE_KEY, status)
  void reload()
}

function resetFilters() {
  keyword.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function closeDialog() {
  dialog.value = ''
  dialogError.value = ''
  dialogLoading.value = false
  submitTarget.value = null
  voidTarget.value = null
  voidReason.value = ''
  detail.value = null
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams({ status: activeGroup.value })
  if (keyword.value.trim()) {
    query.set('keyword', keyword.value.trim())
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('巡查单列表读取失败')
    }
    const payload = (await response.json()) as { items?: Row[]; total?: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '巡查任务列表读取失败'
  }
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (response.ok) {
      stats.value = (await response.json()) as StatsPayload
    }
  } catch {
    // 汇总读取失败时保留上一次的卡片数据，不阻断列表操作。
  }
}

async function postAction(
  entryId: string | number,
  values: Record<string, string | number>,
  remark?: string,
): Promise<boolean> {
  dialogError.value = ''
  dialogLoading.value = true
  try {
    const response = await request(`${ENDPOINT}/${entryId}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values, remark }),
    })
    const payload = (await response.json()) as ActionResponse
    if (!response.ok || !payload.ok) {
      dialogError.value = payload.message || '巡查任务动作未生效，请稍后重试'
      return false
    }
    closeDialog()
    await Promise.all([reload(), reloadStats()])
    return true
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '巡查任务操作失败'
    return false
  } finally {
    dialogLoading.value = false
  }
}

function dispatchRow(row: Row) {
  void postAction(String(row.id), { action: '派发巡查' })
}

function openCreate() {
  createForm.value = { 巡查单号: '', 巡查路线: '', 巡查人员: '', 巡查日期: '' }
  dialogError.value = ''
  dialog.value = 'create'
}

async function submitCreate() {
  const form = createForm.value
  const missing = ['巡查单号', '巡查路线', '巡查人员'].filter(
    (field) => !String(form[field as keyof typeof form] || '').trim(),
  )
  if (missing.length) {
    dialogError.value = `请填写必填项：${missing.join('、')}`
    return
  }
  dialogLoading.value = true
  dialogError.value = ''
  try {
    const values: Record<string, string> = {
      巡查单号: form.巡查单号.trim(),
      巡查路线: form.巡查路线.trim(),
      巡查人员: form.巡查人员.trim(),
    }
    if (form.巡查日期) values.巡查日期 = form.巡查日期
    const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
    const payload = (await response.json()) as ActionResponse
    if (!response.ok || !payload.ok) {
      dialogError.value = payload.message || '巡查单登记失败'
      return
    }
    closeDialog()
    // 新单固定落在待派发分组，切过去让用户立刻看到登记结果。
    if (activeGroup.value !== '待派发') {
      activeGroup.value = '待派发'
      window.localStorage.setItem(GROUP_STORAGE_KEY, '待派发')
    }
    await Promise.all([reload(), reloadStats()])
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '巡查单登记失败'
  } finally {
    dialogLoading.value = false
  }
}

function openSubmit(row: Row) {
  submitTarget.value = row
  submitForm.value = {
    巡查路线: String(row.巡查路线 ?? ''),
    巡查里程: '',
    发现问题数: '',
    巡查时长: '',
  }
  dialogError.value = ''
  dialog.value = 'submit'
}

async function submitResult() {
  if (!submitTarget.value) return
  const form = submitForm.value
  if (!form.巡查路线.trim()) {
    dialogError.value = '提交结果时必须填写巡查路线'
    return
  }
  if (form.巡查里程 === '' || Number.isNaN(Number(form.巡查里程)) || Number(form.巡查里程) < 0) {
    dialogError.value = '请填写不小于 0 的巡查里程'
    return
  }
  const issueCount = Number(form.发现问题数)
  if (form.发现问题数 === '' || Number.isNaN(issueCount) || issueCount < 0 || !Number.isInteger(issueCount)) {
    dialogError.value = '发现问题数必须填写不小于 0 的整数'
    return
  }
  const values: Record<string, string | number> = {
    action: '提交结果',
    巡查路线: form.巡查路线.trim(),
    巡查里程: Number(form.巡查里程),
    发现问题数: issueCount,
  }
  if (form.巡查时长.trim()) values.巡查时长 = form.巡查时长.trim()
  await postAction(String(submitTarget.value.id), values)
}

function openVoid(row: Row) {
  voidTarget.value = row
  voidReason.value = ''
  dialogError.value = ''
  dialog.value = 'void'
}

async function submitVoid() {
  if (!voidTarget.value) return
  if (!voidReason.value.trim()) {
    dialogError.value = '作废巡查必须填写作废原因'
    return
  }
  await postAction(String(voidTarget.value.id), { action: '作废巡查' }, voidReason.value.trim())
}

async function openDetail(row: Row) {
  dialog.value = 'detail'
  dialogError.value = ''
  detail.value = null
  detailLoading.value = true
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as { detail?: string } | null
      throw new Error(payload?.detail || '巡查单详情读取失败')
    }
    detail.value = (await response.json()) as DetailRow
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '巡查单详情读取失败'
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  void reload()
  void reloadStats()
})
</script>

<style scoped>
.group-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.tab-btn {
  border: 1px solid var(--border);
  background: #fff;
  border-radius: 999px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
  color: #334155;
}
.tab-btn.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
}
.tab-count {
  font-style: normal;
  margin-left: 6px;
  font-size: 12px;
  opacity: 0.8;
}
.link-danger {
  color: #b42318;
}
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 30;
  padding: 24px;
}
.modal {
  background: #fff;
  border-radius: 10px;
  width: 520px;
  max-width: 100%;
  max-height: 86vh;
  overflow: auto;
  padding: 18px 22px;
  box-shadow: 0 18px 48px rgba(15, 23, 42, 0.25);
}
.modal-wide {
  width: 680px;
}
.modal-title {
  margin: 0 0 14px;
  font-size: 16px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px 16px;
  margin: 0;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: var(--muted);
}
.field.full {
  grid-column: 1 / -1;
}
.field i {
  color: #b42318;
  font-style: normal;
}
.field input,
.field textarea {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 7px 9px;
  font-size: 13px;
  color: #1f2937;
  font-family: inherit;
}
.field textarea {
  resize: vertical;
}
.modal-tip {
  margin: 0;
  font-size: 12px;
  color: #92400e;
  background: #fef3c7;
  border-radius: 6px;
  padding: 8px 10px;
}
.form-error {
  margin: 0;
  color: #b42318;
  font-size: 12px;
}
.modal-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 2px;
}
.modal-wide .modal-actions {
  margin-top: 14px;
}
.btn.danger {
  background: #b42318;
  border-color: #b42318;
  color: #fff;
}
.status-badge {
  display: inline-block;
  border-radius: 999px;
  padding: 3px 12px;
  font-size: 12px;
  margin-bottom: 12px;
}
.badge-pending { background: #e0ecff; color: #1d4ed8; }
.badge-doing { background: #fef3c7; color: #b45309; }
.badge-done { background: #dcfce7; color: #15803d; }
.badge-void { background: #f1f5f9; color: #64748b; }
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 18px;
  margin: 0 0 16px;
}
.detail-grid dt {
  font-size: 12px;
  color: var(--muted);
}
.detail-grid dd {
  margin: 2px 0 0;
  font-size: 13px;
}
.detail-span {
  grid-column: 1 / -1;
}
.timeline-title {
  margin: 0 0 8px;
  font-size: 14px;
}
.timeline {
  list-style: none;
  margin: 0;
  padding: 0 0 0 14px;
  border-left: 2px solid var(--border);
}
.timeline li {
  position: relative;
  padding: 0 0 12px 12px;
}
.timeline li::before {
  content: '';
  position: absolute;
  left: -19px;
  top: 4px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--brand);
}
.timeline-action {
  font-size: 13px;
  font-weight: 600;
  margin-right: 8px;
}
.timeline-time {
  font-size: 12px;
  color: var(--muted);
}
.timeline-note {
  margin: 2px 0 0;
  font-size: 12px;
  color: #475569;
}
</style>
