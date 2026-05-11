<template>
  <el-container style="min-height: 100vh">
    <el-aside width="200px" style="background: #304156">
      <div style="padding: 20px; text-align: center; color: #fff; font-size: 18px; font-weight: bold">
        📊 投资追踪
      </div>
      <el-menu
        :default-active="$route.path"
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409eff"
        router
      >
        <el-menu-item index="/">
          <span>总览</span>
        </el-menu-item>
        <el-menu-item index="/trades">
          <span>交易记录</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <span>收益统计</span>
        </el-menu-item>
        <el-menu-item index="/analysis">
          <span>📈 行情分析</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main style="background: #f0f2f5; padding: 20px">
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup>
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
</style>
