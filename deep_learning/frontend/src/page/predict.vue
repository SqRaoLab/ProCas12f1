<script setup lang="ts">
import {defineComponent, reactive, provide} from 'vue'

import MyForm from "../components/form.vue";
import MyTable from "../components/table.vue";
import MyStatus from "../components/status.vue";

import type {State} from "../interfaces.ts";

defineComponent({
  components: {MyForm, MyTable}
})

// 创建局部共享状态（仅在此组件树内有效）
const sharedState = reactive<State>({
  task_id: null,
  status: null,
  pagination: {
      order: "desc",  order_by: "indel_freq",
      total: 10,  length: 10,  page: 1
  }
});

// 提供给所有后代组件
provide('sharedState', sharedState);

</script>

<template>
  <my-form />
  <div v-if="sharedState.task_id !== null && sharedState.task_id !== undefined && sharedState.task_id !== ''">
    <n-grid cols="6">
      <n-gi :span="1">
        <n-divider>Status</n-divider>
        <my-status />
      </n-gi>
      <n-gi :span="5">
        <n-divider>Results</n-divider>
        <my-table v-if="sharedState.status !== null && sharedState.status.status === 'completed'" />
      </n-gi>
    </n-grid>
  </div>
</template>

<style scoped>

</style>
