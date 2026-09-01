<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  title: { type: String, default: '' },
  xAxis: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] }, // [{name, data, color?, area?}]
  unit: { type: String, default: '' },
  height: { type: String, default: '280px' },
  yName: { type: String, default: '' },
})

const chartRef = ref()
let chart = null

function render() {
  if (!chart) return
  const series = props.series.map((s) => ({
    name: s.name,
    type: 'line',
    smooth: true,
    showSymbol: false,
    data: s.data,
    itemStyle: s.color ? { color: s.color } : undefined,
    areaStyle: s.area ? { opacity: 0.15 } : undefined,
  }))
  chart.setOption(
    {
      title: { text: props.title, left: 10, textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: 'axis',
        valueFormatter: (v) => (v === null || v === undefined ? '-' : `${v} ${props.unit}`),
      },
      legend: { top: 4, right: 10 },
      grid: { left: 50, right: 20, top: 40, bottom: 30 },
      xAxis: { type: 'category', data: props.xAxis, boundaryGap: false },
      yAxis: { type: 'value', name: props.yName },
      series,
    },
    true,
  )
}

function resize() {
  chart && chart.resize()
}

onMounted(() => {
  chart = echarts.init(chartRef.value)
  render()
  window.addEventListener('resize', resize)
})

watch([() => props.xAxis, () => props.series], render)

function dispose() {
  window.removeEventListener('resize', resize)
  chart && chart.dispose()
  chart = null
}

onBeforeUnmount(dispose)
</script>

<template>
  <div ref="chartRef" class="metric-chart" :style="{ height }"></div>
</template>

<style scoped>
.metric-chart {
  width: 100%;
}
</style>
