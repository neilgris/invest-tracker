<template>
  <el-container style="min-height: 100vh">
    <el-aside width="140px" style="background: #304156; flex-shrink: 0">
      <div style="padding: 16px 10px; text-align: center; color: #fff; font-size: 16px; font-weight: bold">
        📊 投资追踪
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
        style="border-right: none"
      >
        <el-menu-item index="/">
          <el-icon><Home-Filled /></el-icon>
          <span>总览</span>
        </el-menu-item>
        <el-menu-item index="/trades">
          <el-icon><List /></el-icon>
          <span>交易</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><Trend-Charts /></el-icon>
          <span>统计</span>
        </el-menu-item>
        <el-menu-item index="/analysis">
          <el-icon><Data-Line /></el-icon>
          <span>行情</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main style="background: #f0f2f5; padding: 20px">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
import { HomeFilled, List, TrendCharts, DataLine } from '@element-plus/icons-vue'
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
</style>
