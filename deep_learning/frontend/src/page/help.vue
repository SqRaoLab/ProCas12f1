<script setup lang="ts">
import type {SelectOption} from "naive-ui"
import {ref} from "vue"
import {BASE_URL} from "../utils.ts";


const data = ref<SelectOption[]>([
  {
    label: "Create new task under `New Task` page",
    value: `${BASE_URL}/help/help1.png`
  },
  {
    label: "1. Choose your PAM first",
    value: `${BASE_URL}/help/help2.png`
  },
  {
    label: "2. Choose genome version to use",
    value: `${BASE_URL}/help/help3.png`
  },
  {
    label: "3. Provide design targets through different ways",
    value: `${BASE_URL}/help/help4.png`
  },
  {
    label: "4. Start typing a gene name or ID (minimum 3 characters). Matching genes will appear—choose the one you want.",
    value: `${BASE_URL}/help/help5.png`
  },
  {
    label: "5. Input genomic region.",
    value: `${BASE_URL}/help/help6.png`
  },
  {
    label: "6. Custom sequences can be submitted either as one sequence per line or in standard FASTA format.",
    value: `${BASE_URL}/help/help7.png`
  },
  {
    label: "7. After submit task, the task id, running status and results will listed blow",
    value: `${BASE_URL}/help/help8.png`
  },
  {
    label: "8. Results can be retrieved at a later time by providing the corresponding task ID.",
    value: `${BASE_URL}/help/help9.png`
  },
])

</script>

<template>
  <n-grid x-gap="10" y-gap="10" cols="1">
    <n-gi span="1" >
    <n-tabs type="card" placement="left" animated>
      <n-tab-pane name="Help" tab="Help">
        <div v-for="row of data" :key="row.label">
          <n-card :title="row.label" hoverable>
            <n-image :src="row.value" width="100%" />
          </n-card>
          <n-divider />
        </div>
      </n-tab-pane>
      <n-tab-pane name="Contact" tab="Contact">
        <n-descriptions label-placement="left" bordered :column="1">
          <n-descriptions-item>
            <template #label>
              Maintainer (Website usage issues)
            </template>
            zhangyiming@ihcams.ac.cn
          </n-descriptions-item>
          <n-descriptions-item>
            <template #label>
              Corresponding author
            </template>
            raoshuquan@ihcams.ac.cn
          </n-descriptions-item>
        </n-descriptions>
      </n-tab-pane>
    </n-tabs>
    </n-gi>
  </n-grid>
</template>

<style scoped>

</style>
