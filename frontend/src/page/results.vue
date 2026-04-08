<script setup lang="ts">
import { defineComponent, reactive, provide, ref } from 'vue'

import MyForm from "../components/form.vue";
import MyTable from "../components/table.vue";
import MyStatus from "../components/status.vue";
import {AddTaskFilled, ContentPasteSearchOutlined} from "@vicons/material";
import type {State} from "../interfaces.ts";

defineComponent({
  components: {MyForm, MyTable}
})

// Kqp4l45booKVzEAU
const task_id = ref<string | null>(null)
const example_id = 'JFcriFnGUv8yyj_b'


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
  <n-form label-placement="left">
    <n-grid :cols="4" :x-gap="10">
      <n-gi :span="3">
        <n-form-item label="Task ID">
          <n-input v-model:value="task_id" />
        </n-form-item>
      </n-gi>
      <n-gi :span="1">
        <n-form-item>
          <n-button-group>
            <n-button type="success" @click="sharedState.task_id = task_id; sharedState.status = null">
              <template #icon>
                  <n-icon><AddTaskFilled /></n-icon>
              </template>
              Submit
            </n-button>
            <n-button type="info" @click="task_id = example_id; sharedState.status = null">
              <template #icon>
                  <n-icon><ContentPasteSearchOutlined /></n-icon>
              </template>
              Example
            </n-button>
          </n-button-group>

        </n-form-item>
      </n-gi>
    </n-grid>

  </n-form>

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
.read-the-docs {
  color: #888;
}
</style>
