<script setup lang="ts">
defineProps<{ stage: string; message: string }>()

const STAGES: Record<string, string> = {
  submitting: '提交中',
  searching_attractions: '搜索景点',
  enriching: '补充图片',
  planning: '规划行程',
  completed: '完成',
}
</script>

<template>
  <div class="progress">
    <div class="orb" />
    <div class="orb-glow" />
    <p class="msg">{{ message }}</p>
    <div class="stages">
      <div
        v-for="(label, key) in STAGES"
        :key="key"
        class="stage-pill"
        :class="{
          active: stage === key,
          done: STAGES[stage] && stage !== '' && Object.keys(STAGES).indexOf(stage) > Object.keys(STAGES).indexOf(key),
        }"
      >
        {{ label }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
  padding: 60px 20px;
  position: relative;
}
.orb {
  width: 56px; height: 56px;
  border-radius: 50%;
  background: conic-gradient(from 0deg, var(--accent), var(--accent-2), var(--accent-4), var(--accent));
  -webkit-mask: radial-gradient(circle at 50% 50%, transparent 60%, #000 62%);
  mask: radial-gradient(circle at 50% 50%, transparent 60%, #000 62%);
  animation: spin 1.2s linear infinite;
}
.orb-glow {
  position: absolute;
  top: calc(50% - 130px);
  width: 120px; height: 120px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(10, 132, 255, 0.25), transparent 70%);
  pointer-events: none;
  animation: pulse 2s ease-in-out infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.15); }
}
.msg {
  font-size: 16px;
  color: var(--text);
  font-weight: 500;
  margin: 0;
  text-align: center;
}
.stages { display: flex; flex-wrap: wrap; gap: 8px; justify-content: center; }
.stage-pill {
  font-size: 12px;
  padding: 6px 14px;
  border-radius: var(--radius-pill);
  background: rgba(255, 255, 255, 0.06);
  color: var(--muted);
  border: 1px solid var(--glass-border);
  transition: all 0.18s ease;
}
.stage-pill.active {
  background: linear-gradient(135deg, var(--accent), var(--accent-2));
  color: #fff;
  border-color: transparent;
  box-shadow: 0 4px 14px rgba(10, 132, 255, 0.35);
}
.stage-pill.done {
  background: rgba(48, 209, 88, 0.14);
  color: var(--ok);
  border-color: rgba(48, 209, 88, 0.3);
}
</style>