<script setup lang="ts">
import type { MenuOption } from 'naive-ui'
import type { Component } from 'vue'

import { RouterLink } from 'vue-router'

import {
  AddTaskRound,
  CloudUploadOutlined,
  DataThresholdingOutlined,
  HelpOutlineTwotone,
  HomeOutlined,
} from '@vicons/material'

import { NIcon } from 'naive-ui'
import { h, ref } from 'vue'

const activeKey = ref<string | null>(null)

function renderIcon(icon: Component) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const menuOptions: MenuOption[] = [
  {
    label: () =>
      h(
        RouterLink,
        {to: {name: "Home"} },
          {default: () => 'Home'}
      ),
    key: 'home',
    icon: renderIcon(HomeOutlined)
  },
  {
    label: () =>
      h(
        RouterLink,
        {to: {name: "Prediction"} },
        {default: () => 'New task'}
      ),
    key: 'predict',
    icon: renderIcon(AddTaskRound)
  },
  {
    label: () =>
      h(
        RouterLink,
        {to: {name: "Results"}},
        {default: () => 'Retrieve results'}
      ),
    key: 'results',
    icon: renderIcon(DataThresholdingOutlined)
  },
  {
    label: () =>
      h(
        RouterLink,
        {to: {name: "Upload"}},
        {default: () => 'Upload'}
      ),
    key: 'upload',
    icon: renderIcon(CloudUploadOutlined)
  },
  {
    label: () =>
      h(
        RouterLink,
        {to: {name: "Help"}},
        {default: () => 'Help'}
      ),
    key: 'help',
    icon: renderIcon(HelpOutlineTwotone)
  },
]
</script>


<template >
  <n-config-provider>
    <n-message-provider>
      <n-space justify="center" size="large" style="background-color: #B2D8EE">
        <n-menu style="margin-top: 20px"
          size="large"
          v-model:value="activeKey"
          mode="horizontal"
          :options="menuOptions"
          responsive
          :icon-size="30"
        />
      </n-space>
       <n-divider />

      <n-grid cols="10">
        <n-gi :offset="1" :span="8">
          <router-view />
        </n-gi>
      </n-grid>
    </n-message-provider>
  </n-config-provider>

</template>

<style scoped>

</style>