<template>
  <ClientOnly>
    <div ref="el" :style="{ height: height, width: '100%' }" />
    <template #fallback>
      <div :style="{ height: height }" class="bg-[#0d1117] rounded-lg animate-pulse" />
    </template>
  </ClientOnly>
</template>

<script setup lang="ts">
import { init, use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  GridComponent,
  DataZoomComponent,
  LegendComponent,
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, TooltipComponent, GridComponent, DataZoomComponent, LegendComponent, CanvasRenderer])

const props = withDefaults(defineProps<{
  option: Record<string, any>
  height?: string
}>(), {
  height: '200px',
})

const el = ref<HTMLDivElement | null>(null)
let chart: ReturnType<typeof init> | null = null

function resize() { chart?.resize() }

// flush:'post' ensures DOM is fully painted before we read container dimensions.
// chart.resize() after setOption forces ECharts to pick up the actual width/height
// instead of the 0px it would read during the initial layout pass.
watch(el, async (newEl) => {
  if (!newEl) return
  await nextTick()
  chart = init(newEl, null, { renderer: 'canvas' })
  chart.setOption(props.option)
  chart.resize()
  window.addEventListener('resize', resize)
}, { flush: 'post' })

onUnmounted(() => {
  chart?.dispose()
  chart = null
  window.removeEventListener('resize', resize)
})

watch(() => props.option, (opt) => {
  if (!chart) return
  chart.setOption(opt, { notMerge: true })
  chart.resize()
}, { deep: true, flush: 'post' })
</script>
