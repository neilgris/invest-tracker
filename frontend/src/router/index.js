import { createRouter, createWebHistory } from 'vue-router'
import Overview from '../views/Overview.vue'
import Trades from '../views/Trades.vue'
import PositionDetail from '../views/PositionDetail.vue'
import Stats from '../views/Stats.vue'
import Analysis from '../views/Analysis.vue'

const routes = [
  { path: '/', name: 'Overview', component: Overview },
  { path: '/trades', name: 'Trades', component: Trades },
  { path: '/position/:code', name: 'PositionDetail', component: PositionDetail },
  { path: '/stats', name: 'Stats', component: Stats },
  { path: '/analysis', name: 'Analysis', component: Analysis },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
