<template>
  <div class="share-embed">
    <button @click="open = !open" class="toggle-btn">
      <span class="icon">{{ open ? '▲' : '▼' }}</span>
      Embed & Download
    </button>

    <div v-if="open" class="panel">
      <!-- Embed -->
      <div class="section">
        <div class="section-label">Embed this chart</div>
        <div class="code-wrap">
          <code class="snippet">{{ iframeCode }}</code>
          <button @click="copyEmbed" class="copy-btn">{{ copiedEmbed ? 'Copied!' : 'Copy' }}</button>
        </div>
        <div class="preview-link">
          <a :href="embedUrl" target="_blank" rel="noopener" class="link">Preview ↗</a>
        </div>
      </div>

      <!-- Download -->
      <div class="section">
        <div class="section-label">Download data</div>
        <a :href="downloadUrl" class="download-btn">
          ↓ Download CSV
        </a>
        <div class="attribution">Source: MetricsHour · metricshour.com</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
const props = defineProps<{
  embedUrl: string
  downloadUrl: string
}>()

const open = ref(false)
const copiedEmbed = ref(false)

const iframeCode = computed(() =>
  `<iframe src="https://metricshour.com${props.embedUrl}" width="600" height="420" frameborder="0" style="border-radius:8px;" title="MetricsHour Data"></iframe>`
)

async function copyEmbed() {
  try {
    await navigator.clipboard.writeText(iframeCode.value)
    copiedEmbed.value = true
    setTimeout(() => { copiedEmbed.value = false }, 2000)
  } catch {}
}
</script>

<style scoped>
.share-embed { margin-top: 16px; }

.toggle-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid #1f2937;
  color: #6b7280;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s;
}
.toggle-btn:hover { border-color: #374151; color: #9ca3af; }
.icon { font-size: 9px; }

.panel {
  margin-top: 10px;
  background: #0d1117;
  border: 1px solid #1f2937;
  border-radius: 10px;
  padding: 14px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.section-label {
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #4b5563;
  margin-bottom: 8px;
}

.code-wrap {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  background: #111827;
  border: 1px solid #1f2937;
  border-radius: 6px;
  padding: 8px 10px;
}

.snippet {
  flex: 1;
  font-size: 11px;
  color: #9ca3af;
  font-family: 'SF Mono', 'Fira Code', monospace;
  word-break: break-all;
  line-height: 1.5;
}

.copy-btn {
  background: #1f2937;
  border: 1px solid #374151;
  color: #d1d5db;
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: background 0.2s;
}
.copy-btn:hover { background: #374151; }

.preview-link { margin-top: 6px; }
.link { font-size: 11px; color: #4b5563; text-decoration: none; }
.link:hover { color: #10b981; }

.download-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: #111827;
  border: 1px solid #1f2937;
  color: #10b981;
  font-size: 12px;
  font-weight: 600;
  padding: 7px 14px;
  border-radius: 6px;
  text-decoration: none;
  transition: border-color 0.2s, background 0.2s;
}
.download-btn:hover { border-color: #10b981; background: rgba(16,185,129,0.05); }

.attribution {
  margin-top: 6px;
  font-size: 10px;
  color: #374151;
}
</style>
