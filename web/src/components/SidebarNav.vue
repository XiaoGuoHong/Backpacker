<script setup lang="ts">
import type { ItineraryDay } from '../types'

defineProps<{ days: ItineraryDay[]; active: number }>()
const emit = defineEmits<{ (e: 'select', index: number): void }>()
</script>

<template>
  <nav class="sidebar">
    <h3>日程导航</h3>
    <ol>
      <li
        v-for="d in days"
        :key="d.index"
        :class="{ active: d.index === active }"
        @click="emit('select', d.index)"
      >
        <span class="idx">Day {{ d.index }}</span>
        <span class="date">{{ d.date }}</span>
        <span class="count">{{ d.attractions.length }} 景点</span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.sidebar { background: var(--panel); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
h3 { margin: 0; }
ol { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
li { display: flex; align-items: center; gap: 8px; padding: 8px 10px; border-radius: 8px; cursor: pointer; font-size: 13px; }
li:hover { background: var(--bg); }
li.active { background: var(--user); color: #fff; }
.idx { font-weight: 700; }
.date { color: var(--muted); flex: 1; }
li.active .date { color: rgba(255,255,255,0.85); }
.count { font-size: 12px; color: var(--muted); }
li.active .count { color: rgba(255,255,255,0.85); }
</style>