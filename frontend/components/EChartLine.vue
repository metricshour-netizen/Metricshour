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
let ro: ResizeObserver | null = null

// ResizeObserver fires whenever the container changes size (including initial layout).
// This is more reliable than window resize + nextTick for catching 0-width init issues.
watch(el, (newEl) => {
  if (!newEl) return

  chart = init(newEl, null, { renderer: 'canvas' })
  chart.setOption(props.option)

  ro = new ResizeObserver(() => {
    chart?.resize()
  })
  ro.observe(newEl)
  // Fire one manual resize after the first paint to handle any deferred layout
  requestAnimationFrame(() => chart?.resize())
}, { flush: 'post' })

onUnmounted(() => {
  ro?.disconnect()
  ro = null
  chart?.dispose()
  chart = null
})

watch(() => props.option, (opt) => {
  if (!chart) return
  chart.setOption(opt, { notMerge: true })
  chart.resize()
}, { deep: true, flush: 'post' })
</script>
