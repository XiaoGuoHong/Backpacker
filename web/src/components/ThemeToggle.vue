<script setup lang="ts">
import { onMounted, ref } from 'vue'

const theme = ref<'light' | 'dark'>('dark')

function apply(t: 'light' | 'dark') {
  theme.value = t
  document.documentElement.setAttribute('data-theme', t)
  try { localStorage.setItem('bp-theme', t) } catch {}
}

function toggle() {
  apply(theme.value === 'dark' ? 'light' : 'dark')
}

onMounted(() => {
  let saved: 'light' | 'dark' | null = null
  try { saved = localStorage.getItem('bp-theme') as any } catch {}
  if (saved === 'light' || saved === 'dark') {
    apply(saved)
  } else {
    const prefersLight = window.matchMedia('(prefers-color-scheme: light)').matches
    apply(prefersLight ? 'light' : 'dark')
  }
})
</script>

<template>
  <button class="toggle" :title="theme === 'dark' ? '切换到浅色' : '切换到深色'" @click="toggle">
    <svg v-if="theme === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="4.5" fill="currentColor" />
      <g stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
        <line x1="12" y1="2.5" x2="12" y2="5" />
        <line x1="12" y1="19" x2="12" y2="21.5" />
        <line x1="2.5" y1="12" x2="5" y2="12" />
        <line x1="19" y1="12" x2="21.5" y2="12" />
        <line x1="5.2" y1="5.2" x2="7" y2="7" />
        <line x1="17" y1="17" x2="18.8" y2="18.8" />
        <line x1="5.2" y1="18.8" x2="7" y2="17" />
        <line x1="17" y1="7" x2="18.8" y2="5.2" />
      </g>
    </svg>
    <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none">
      <path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round" />
    </svg>
  </button>
</template>

<style scoped>
.toggle {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: 1px solid var(--glass-border);
  background: var(--glass-input);
  color: var(--text-2);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.18s ease;
}
.toggle:hover {
  background: var(--glass-hover);
  color: var(--text);
}
</style>