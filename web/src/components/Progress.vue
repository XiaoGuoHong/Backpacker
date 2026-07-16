<script setup lang="ts">
defineProps<{ stage: string; message: string }>()
</script>

<template>
  <div class="progress">
    <div class="spinner" />
    <p class="msg">{{ message }}</p>
  </div>
</template>

<style scoped>
.progress { display: flex; flex-direction: column; align-items: center; gap: 16px; padding: 32px; }
.spinner {
  width: 36px; height: 36px; border-radius: 50%;
  border: 3px solid var(--bubble); border-top-color: var(--user);
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.msg { color: var(--muted); }
</style>