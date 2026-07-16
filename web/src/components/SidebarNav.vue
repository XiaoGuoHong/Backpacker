<script setup lang="ts">
import type { ItineraryDay } from '../types'

defineProps<{ days: ItineraryDay[]; active: number }>()
const emit = defineEmits<{ (e: 'select', index: number): void }>()
</script>

<template>
  <nav class="sidebar glass">
    <div class="head">
      <span class="dot" />
      <h3>日程</h3>
    </div>
    <ol>
      <li
        v-for="d in days"
        :key="d.index"
        :class="{ active: d.index === active }"
        @click="emit('select', d.index)"
      >
        <span class="idx">D{{ d.index }}</span>
        <div class="info">
          <span class="date">{{ d.date }}</span>
          <span class="count">{{ d.attractions.length }} 个景点</span>
        </div>
        <span v-if="d.weather" class="w-mini">{{ d.weather.day_desc || '—' }}</span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.sidebar {
  border-radius: var(--radius-lg);
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(1.4);
  -webkit-backdrop-filter: blur(20px) saturate(1.4);
  border: 1px solid var(--glass-border);
  box-shadow: var(--shadow-1);
}
.head { display: flex; align-items: center; gap: 8px; padding: 0 4px; }
.dot {
  width: 8px; height: 8px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--accent-4), var(--accent-2));
}
h3 { margin: 0; font-size: 15px; font-weight: 600; }
ol {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  font-size: 13px;
  border: 1px solid transparent;
  transition: all 0.18s ease;
}
li:hover { background: rgba(255, 255, 255, 0.06); }
li.active {
  background: linear-gradient(135deg, rgba(10, 132, 255, 0.20), rgba(191, 90, 242, 0.16));
  border-color: rgba(10, 132, 255, 0.32);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.06);
}
.idx {
  font-size: 11px;
  font-weight: 700;
  color: var(--accent);
  width: 28px;
  flex-shrink: 0;
}
li.active .idx { color: var(--text); }
.info { display: flex; flex-direction: column; gap: 2px; flex: 1; min-width: 0; }
.date { font-size: 13px; color: var(--text-2); font-weight: 500; }
.count { font-size: 11px; color: var(--muted); }
.w-mini {
  font-size: 11px;
  color: var(--accent-4);
  white-space: nowrap;
}
</style>