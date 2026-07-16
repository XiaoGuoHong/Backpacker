<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import PlanForm from './components/PlanForm.vue'
import Progress from './components/Progress.vue'
import ItineraryDay from './components/ItineraryDay.vue'
import MapView from './components/MapView.vue'
import BudgetPanel from './components/BudgetPanel.vue'
import SidebarNav from './components/SidebarNav.vue'
import ExportBar from './components/ExportBar.vue'
import {
  fetchConfig,
  fetchHealth,
  fetchItinerary,
  fetchMetrics,
  plan,
  pollItinerary,
  subscribeEvents,
} from './api'
import type {
  BudgetBreakdown,
  ItineraryDay as ItineraryDayType,
  PlanResult,
  TripRequest,
} from './types'

type Phase = 'form' | 'progress' | 'result'

const phase = ref<Phase>('form')
const stage = ref('')
const progressMsg = ref('')
const errorMsg = ref('')
const result = ref<PlanResult | null>(null)
const amapJsKey = ref<string | null>(null)

const health = ref<{ status: string; text: string }>({ status: '', text: '健康检测中…' })
const metricsText = ref('')

const editable = computed(() => phase.value === 'result' && result.value?.status !== 'failed')
const days = computed<ItineraryDayType[]>(() => result.value?.itinerary?.days || [])
const budget = computed<BudgetBreakdown>(
  () =>
    result.value?.itinerary?.budget || {
      ticket: 0,
      hotel: 0,
      food: 0,
      transport: 0,
      total: 0,
      currency: 'CNY',
    },
)
const activeDay = ref(1)
const navOpen = ref(false)

let timer: number | undefined

async function startPlan(req: TripRequest) {
  phase.value = 'progress'
  errorMsg.value = ''
  progressMsg.value = '正在提交行程请求…'
  stage.value = 'submitting'
  try {
    const accepted = await plan(req)
    stage.value = 'searching_attractions'
    subscribeEvents(accepted.task_id, {
      onStage: (s, msg) => {
        stage.value = s
        progressMsg.value = msg
      },
      onError: (msg) => {
        errorMsg.value = msg
      },
    })
    const polled = await pollItinerary(accepted.task_id, 120000)
    const final = polled || (await fetchItinerary(accepted.task_id))
    if (!final) {
      errorMsg.value = '未能获取行程结果'
      phase.value = 'form'
      return
    }
    result.value = final
    activeDay.value = final.itinerary?.days[0]?.index || 1
    phase.value = 'result'
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : '规划请求失败'
    phase.value = 'form'
  }
}

function recomputeBudget(): BudgetBreakdown {
  const daysList = result.value?.itinerary?.days || []
  let ticket = 0
  let hotel = 0
  daysList.forEach((d) => {
    d.attractions.forEach((a) => {
      ticket += a.ticket_price || 0
    })
    if (d.hotel?.price_per_night) hotel += d.hotel.price_per_night
  })
  const base = result.value?.itinerary?.budget
  const food = base?.food || 0
  const transport = base?.transport || 0
  const currency = base?.currency || 'CNY'
  return { ticket, hotel, food, transport, total: ticket + hotel + food + transport, currency }
}

function removeAttraction(dayIndex: number, attrIndex: number) {
  const day = result.value?.itinerary?.days.find((d) => d.index === dayIndex)
  if (!day) return
  day.attractions.splice(attrIndex, 1)
  if (result.value?.itinerary) result.value.itinerary.budget = recomputeBudget()
}

function reorderAttraction(dayIndex: number, from: number, to: number) {
  const day = result.value?.itinerary?.days.find((d) => d.index === dayIndex)
  if (!day) return
  const [moved] = day.attractions.splice(from, 1)
  day.attractions.splice(to, 0, moved)
}

function scrollToDay(index: number) {
  activeDay.value = index
  const el = document.getElementById(`day-${index}`)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  navOpen.value = false
}

function reset() {
  phase.value = 'form'
  result.value = null
  errorMsg.value = ''
  progressMsg.value = ''
  stage.value = ''
}

async function refreshStatus() {
  try {
    const h = await fetchHealth()
    const ok = h.status === 'ok'
    health.value = { status: ok ? 'ok' : 'warn', text: ok ? '服务可用' : '服务降级' }
    const m = await fetchMetrics()
    const okCount = Object.values(m.by_type || {}).reduce((a, b) => a + (b.success || 0), 0)
    metricsText.value = `${m.total || 0} 查询 / ${okCount} 成功`
  } catch {
    health.value = { status: 'warn', text: '无法连接' }
  }
}

onMounted(async () => {
  refreshStatus()
  timer = window.setInterval(refreshStatus, 30000)
  try {
    const cfg = await fetchConfig()
    amapJsKey.value = cfg.amap_js_key
  } catch {
    amapJsKey.value = null
  }
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="app">
    <header class="topbar glass">
      <div class="brand">
        <span class="logo">🎒</span>
        <h1>Backpacker</h1>
      </div>
      <div class="status">
        <span class="pill" :class="health.status">{{ health.text }}</span>
        <span v-if="metricsText" class="pill muted">{{ metricsText }}</span>
      </div>
    </header>

    <div v-if="errorMsg" class="alert">
      <p>{{ errorMsg }}</p>
      <button class="ghost small" @click="errorMsg = ''">关闭</button>
    </div>

    <main class="content">
      <!-- 表单页 -->
      <section v-if="phase === 'form'" class="hero">
        <div class="hero-head">
          <span class="eyebrow">智能旅行行程规划器</span>
          <h2>规划一段<em>属于你的</em>旅程</h2>
          <p class="lede">输入目的地、偏好与预算，多个智能体协同为你生成含景点 · 天气 · 酒店的多日行程。</p>
        </div>
        <PlanForm @submit="startPlan" />

        <div v-if="result?.status === 'failed'" class="failed-note">
          <p>{{ result?.error_message || '上次规划失败，请重新尝试。' }}</p>
          <button class="ghost" @click="reset">重新规划</button>
        </div>
      </section>

      <!-- 加载态 -->
      <section v-else-if="phase === 'progress'" class="progress-wrap">
        <Progress :stage="stage" :message="progressMsg || '正在处理…'" />
      </section>

      <!-- 结果页 -->
      <section v-else class="result">
        <div class="result-shell">
          <aside class="rail">
            <div class="rail-card glass">
              <div class="rail-head">
                <p class="trip-summary">{{ result?.condition_summary }}</p>
                <span v-if="result?.itinerary?.is_demo" class="badge">演示数据</span>
              </div>
              <ExportBar />
              <button class="ghost full" @click="reset">← 重新规划</button>
            </div>
            <SidebarNav :days="days" :active="activeDay" @select="scrollToDay" />
          </aside>

          <div class="body" id="result-capture">
            <div class="map-budget">
              <MapView :days="days" :amap-js-key="amapJsKey" />
              <BudgetPanel :budget="budget" />
            </div>

            <div v-if="result?.itinerary?.notes?.length" class="notes glass">
              <h3>规划说明</h3>
              <ul>
                <li v-for="(n, i) in result.itinerary.notes" :key="i">{{ n }}</li>
              </ul>
              <div class="notes-foot">
                <p v-if="result.hints" class="muted">{{ result.hints }}</p>
                <p v-if="result.request_id" class="muted">request_id · {{ result.request_id }}</p>
              </div>
            </div>

            <div class="days">
              <ItineraryDay
                v-for="d in days"
                :key="d.index"
                :day="d"
                :editable="editable"
                @remove-attraction="(i) => removeAttraction(d.index, i)"
                @reorder="(from, to) => reorderAttraction(d.index, from, to)"
              />
            </div>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>

<style scoped>
.app {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.glass {
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-1);
}

/* 顶栏 */
.topbar {
  padding: 14px 28px;
  border-radius: 0;
  border-left: none;
  border-right: none;
  border-top: none;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  position: sticky;
  top: 0;
  z-index: 50;
}
.brand { display: flex; align-items: center; gap: 10px; }
.logo { font-size: 22px; }
.topbar h1 {
  font-size: 17px;
  font-weight: 600;
  margin: 0;
  letter-spacing: -0.02em;
}
.status { display: flex; gap: 8px; }
.pill {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.08);
  color: var(--text-2);
}
.pill.muted { color: var(--muted); }
.pill.ok { color: var(--ok); }
.pill.warn { color: var(--warn); }

/* 警示 */
.alert {
  max-width: 920px;
  margin: 16px auto 0;
  padding: 12px 16px;
  border-radius: var(--radius);
  background: rgba(255, 69, 58, 0.16);
  border: 1px solid rgba(255, 69, 58, 0.4);
  color: #ffccc8;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}
.alert p { margin: 0; }

/* 内容区 */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 40px 28px 80px;
}

/* Hero */
.hero {
  max-width: 720px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 40px;
}
.hero-head { text-align: center; }
.eyebrow {
  display: inline-block;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 14px;
}
.hero-head h2 {
  font-size: 36px;
  font-weight: 700;
  margin: 0;
  letter-spacing: -0.03em;
}
.hero-head h2 em {
  font-style: italic;
  background: linear-gradient(120deg, var(--accent), var(--accent-2) 70%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.lede {
  max-width: 540px;
  margin: 14px auto 0;
  color: var(--muted);
  font-size: 15px;
  line-height: 1.6;
}
.failed-note {
  margin-top: 24px;
  padding: 20px;
  border-radius: var(--radius-lg);
  background: rgba(255, 69, 58, 0.10);
  border: 1px solid rgba(255, 69, 58, 0.3);
  text-align: center;
  color: #ffccc8;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
}

.progress-wrap {
  max-width: 720px;
  margin: 60px auto 0;
}

/* 结果 */
.result {
  max-width: 1180px;
  margin: 0 auto;
}
.result-shell {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 20px;
}
.rail {
  display: flex;
  flex-direction: column;
  gap: 16px;
  position: sticky;
  top: 88px;
  align-self: start;
  max-height: calc(100vh - 110px);
  overflow-y: auto;
  padding-right: 4px;
}
.rail-card {
  border-radius: var(--radius-lg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.rail-head { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.trip-summary {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  flex: 1;
}
.badge {
  background: linear-gradient(135deg, var(--accent-2), var(--accent));
  color: #fff;
  font-size: 11px;
  padding: 3px 10px;
  border-radius: var(--radius-pill);
  white-space: nowrap;
}

.body { display: flex; flex-direction: column; gap: 20px; }
.map-budget { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }

.notes {
  border-radius: var(--radius-lg);
  padding: 20px 22px;
  font-size: 13.5px;
}
.notes h3 { margin: 0 0 10px; font-size: 15px; font-weight: 600; }
.notes ul {
  margin: 0;
  padding-left: 18px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--text-2);
}
.notes-foot {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.muted { color: var(--muted); font-size: 12px; margin: 0; }

.days { display: flex; flex-direction: column; gap: 20px; }

.ghost {
  padding: 9px 18px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-2);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.18s ease;
}
.ghost:hover { background: rgba(255, 255, 255, 0.12); border-color: rgba(255, 255, 255, 0.18); }
.ghost.small { padding: 4px 12px; font-size: 12px; }
.ghost.full { width: 100%; text-align: center; }

@media (max-width: 980px) {
  .map-budget { grid-template-columns: 1fr; }
}
@media (max-width: 760px) {
  .content { padding: 24px 16px 60px; }
  .result-shell { grid-template-columns: 1fr; }
  .rail { position: static; max-height: none; }
  .hero-head h2 { font-size: 28px; }
}
</style>