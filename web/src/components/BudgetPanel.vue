<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetBreakdown } from '../types'

const props = defineProps<{ budget: BudgetBreakdown }>()

const COLORS = ['#0a84ff', '#bf5af2', '#30d158', '#ff9f0a']

const segments = computed(() => {
  const b = props.budget
  const items = [
    { label: '门票', value: b.ticket, color: COLORS[0], icon: '🎟' },
    { label: '酒店', value: b.hotel, color: COLORS[1], icon: '🏨' },
    { label: '餐饮', value: b.food, color: COLORS[2], icon: '🍽' },
    { label: '交通', value: b.transport, color: COLORS[3], icon: '🚇' },
  ]
  const total = items.reduce((a, x) => a + (x.value || 0), 0) || 1
  return items.map((x) => ({ ...x, pct: ((x.value || 0) / total) * 100 }))
})

const totalLabel = computed(() => {
  const v = props.budget.total || 0
  return v >= 10000 ? (v / 10000).toFixed(1) + 'w' : v.toString()
})
</script>

<template>
  <section class="budget glass">
    <div class="head">
      <span class="dot" />
      <h3>预算</h3>
    </div>
    <div class="big">
      <span class="amount">{{ totalLabel }}</span>
      <span class="unit">{{ budget.currency }}</span>
    </div>
    <div class="bar">
      <div
        v-for="(seg, i) in segments"
        :key="i"
        class="seg-bar"
        :style="{ width: seg.pct + '%', background: seg.color }"
        :title="`${seg.label} ¥${seg.value}`"
      />
    </div>
    <ul class="legend">
      <li v-for="(seg, i) in segments" :key="i">
        <span class="leg-dot" :style="{ background: seg.color }" />
        <span class="leg-label">{{ seg.label }}</span>
        <span class="leg-val">¥{{ seg.value || 0 }}</span>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.budget {
  border-radius: var(--radius-lg);
  padding: 18px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-1);
}
.head { display: flex; align-items: center; gap: 8px; }
.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-3), var(--accent));
}
h3 { margin: 0; font-size: 15px; font-weight: 600; }
.big {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.amount {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.04em;
  background: linear-gradient(135deg, var(--text) 0%, var(--accent) 100%);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.unit { color: var(--muted); font-size: 14px; font-weight: 500; }
.bar {
  display: flex;
  height: 10px;
  border-radius: var(--radius-pill);
  overflow: hidden;
  background: rgba(255, 255, 255, 0.05);
}
.seg-bar { height: 100%; transition: width 0.3s ease; }
.legend {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.legend li {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
}
.leg-dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}
.leg-label { color: var(--text-2); flex: 1; }
.leg-val { color: var(--text); font-weight: 600; }
</style>