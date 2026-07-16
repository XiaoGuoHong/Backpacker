<script setup lang="ts">
import { computed } from 'vue'
import type { BudgetBreakdown } from '../types'

const props = defineProps<{ budget: BudgetBreakdown }>()

const COLORS = ['#2563eb', '#22c55e', '#f59e0b', '#a855f7']

const segments = computed(() => {
  const b = props.budget
  const items = [
    { label: '门票', value: b.ticket },
    { label: '酒店', value: b.hotel },
    { label: '餐饮', value: b.food },
    { label: '交通', value: b.transport },
  ]
  const total = items.reduce((a, x) => a + (x.value || 0), 0) || 1
  return items.map((x, i) => ({ ...x, pct: ((x.value || 0) / total) * 100, color: COLORS[i] }))
})
</script>

<template>
  <section class="budget">
    <h3>预算明细</h3>
    <ul class="items">
      <li><span>门票</span><span>{{ budget.ticket }} {{ budget.currency }}</span></li>
      <li><span>酒店</span><span>{{ budget.hotel }} {{ budget.currency }}</span></li>
      <li><span>餐饮</span><span>{{ budget.food }} {{ budget.currency }}</span></li>
      <li><span>交通</span><span>{{ budget.transport }} {{ budget.currency }}</span></li>
    </ul>
    <div class="total">
      <span>合计</span>
      <span class="amount">{{ budget.total }} {{ budget.currency }}</span>
    </div>
    <div class="bar">
      <div v-for="(seg, i) in segments" :key="i" class="seg" :style="{ width: seg.pct + '%', background: seg.color }" :title="seg.label" />
    </div>
    <ul class="legend">
      <li v-for="(seg, i) in segments" :key="i">
        <span class="dot" :style="{ background: seg.color }" />{{ seg.label }}
      </li>
    </ul>
  </section>
</template>

<style scoped>
.budget { background: var(--panel); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
h3 { margin: 0; }
.items { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.items li { display: flex; justify-content: space-between; font-size: 14px; }
.total { display: flex; justify-content: space-between; align-items: baseline; padding-top: 8px; border-top: 1px solid var(--bubble); }
.amount { color: var(--user); font-weight: 700; font-size: 18px; }
.bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; background: var(--bg); }
.seg { height: 100%; }
.legend { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 12px; font-size: 12px; color: var(--muted); }
.dot { width: 8px; height: 8px; border-radius: 50%; display: inline-block; margin-right: 4px; vertical-align: middle; }
</style>