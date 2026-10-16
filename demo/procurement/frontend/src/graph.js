import * as engine from 'echarts/core'
import { GraphChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

engine.use([GraphChart, TooltipComponent, LegendComponent, CanvasRenderer])
export { engine }
