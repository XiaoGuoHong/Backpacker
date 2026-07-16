<script setup lang="ts">
import { ref } from 'vue'

const props = withDefaults(defineProps<{ targetId?: string }>(), { targetId: 'result-capture' })

const busy = ref<'pdf' | 'image' | ''>('')

async function getCanvas(): Promise<HTMLCanvasElement> {
  const mod = await import('html2canvas')
  const html2canvas = (mod as any).default ?? (mod as any).html2canvas
  const el = document.getElementById(props.targetId)
  if (!el) throw new Error('找不到可导出的内容区域')
  return await html2canvas(el, {
    backgroundColor: '#1c1c1e',
    useCORS: true,
    scale: window.devicePixelRatio > 1 ? 2 : 1.5,
  })
}

async function exportImage() {
  if (busy.value) return
  busy.value = 'image'
  try {
    const canvas = await getCanvas()
    const link = document.createElement('a')
    link.href = canvas.toDataURL('image/png')
    link.download = `backpacker-itinerary-${Date.now()}.png`
    link.click()
  } finally {
    busy.value = ''
  }
}

async function exportPdf() {
  if (busy.value) return
  busy.value = 'pdf'
  try {
    const canvas = await getCanvas()
    const { jsPDF } = await import('jspdf')
    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({ orientation: 'p', unit: 'mm', format: 'a4' })
    const pageW = pdf.internal.pageSize.getWidth()
    const pageH = pdf.internal.pageSize.getHeight()
    const ratio = canvas.width / canvas.height
    let imgW = pageW
    let imgH = imgW / ratio
    if (imgH > pageH) {
      imgH = pageH
      imgW = imgH * ratio
    }
    pdf.addImage(imgData, 'PNG', (pageW - imgW) / 2, 8, imgW, imgH)
    pdf.save(`backpacker-itinerary-${Date.now()}.pdf`)
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <section class="export-bar">
    <button class="export" :disabled="busy !== ''" @click="exportImage">
      <span class="ico">🖼</span>
      <span>{{ busy === 'image' ? '导出中…' : '导出图片' }}</span>
    </button>
    <button class="export" :disabled="busy !== ''" @click="exportPdf">
      <span class="ico">📄</span>
      <span>{{ busy === 'pdf' ? '导出中…' : '导出 PDF' }}</span>
    </button>
  </section>
</template>

<style scoped>
.export-bar { display: flex; gap: 8px; }
.export {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 9px 12px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius);
  background: rgba(255, 255, 255, 0.06);
  color: var(--text-2);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.18s ease;
}
.export:hover {
  background: rgba(255, 255, 255, 0.12);
  border-color: rgba(255, 255, 255, 0.18);
  color: var(--text);
}
.export:disabled {
  opacity: 0.5;
  cursor: default;
}
.ico { font-size: 15px; }
</style>