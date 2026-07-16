<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetBreakdown } from '../types'

const props = defineProps<{ budget: BudgetBreakdown }>()

const ITEMS = [
  { key: 'ticket', label: '门票', icon: '🎟', desc: '景点门票合计' },
  { key: 'hotel', label: '酒店', icon: '🏨', desc: '全程住宿' },
  { key: 'food', label: '餐饮', icon: '🍽', desc: '每日餐食' },
  { key: 'transport', label: '交通', icon: '🚇', desc: '市内交通' },
] as const

const items = computed(() => {
  const total = props.budget.total || 1
  return ITEMS.map((x) => {
    const value = (props.budget as any)[x.key] as number
    return {
      ...x,
      value,
      pct: Math.round(((value || 0) / total) * 100),
    }
  })
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

    <ul class="items">
      <li v-for="it in items" :key="it.key">
        <span class="ico">{{ it.icon }}</span>
        <div class="mid">
          <span class="label">{{ it.label }}</span>
          <span class="desc">{{ it.desc }} · {{ it.pct }}%</span>
          <div class="track">
            <div class="fill" :style="{ width: it.pct + '%' }" />
          </div>
        </div>
        <span class="val">¥{{ it.value || 0 }}</span>
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
  gap: 14px;
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
  background: var(--accent);
}
h3 { margin: 0; font-size: 15px; font-weight: 600; }
.big {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding-bottom: 4px;
}
.amount {
  font-size: 36px;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: var(--text);
}
.unit { color: var(--muted); font-size: 14px; font-weight: 500; }

.items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
li {
  display: flex;
  align-items: center;
  gap: 12px;
}
.ico {
  font-size: 18px;
  width: 32px; height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--glass-input);
  flex-shrink: 0;
}
.mid {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}
.label { font-size: 14px; font-weight: 600; color: var(--text); }
.desc { font-size: 11.5px; color: var(--muted); }
.track {
  height: 4px;
  border-radius: 999px;
  background: var(--glass-input);
  overflow: hidden;
  margin-top: 2px;
}
.fill {
  height: 100%;
  background: var(--accent);
  border-radius: 999px;
  transition: width 0.3s ease;
}
.val {
  font-size: 15px;
  font-weight: 700;
  color: var(--text);
  white-space: nowrap;
}
</style>