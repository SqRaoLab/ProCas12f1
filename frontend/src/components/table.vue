<script setup lang="ts">
import axios, {AxiosError, type AxiosResponse} from "axios";
import {useMessage, NTag, NPopover} from "naive-ui";
import type { DataTableColumns, DataTableSortState } from 'naive-ui'

import { APIs } from "../utils.ts"
import type { RowData, Header, State } from "../interfaces.ts"
import {onMounted, ref, h, inject} from "vue";

const state = inject<State>('sharedState');
const message = useMessage()
const showError = (error: AxiosError) => {
    if (error.response !== undefined && error.response.data !== null) {
      message.error(String(error.response.data))
    }
}

const table_headers  = ref<Map<string, Header[]>>()
const table_data = ref<RowData[]>([])

// generate headers for different task category
const headers = ref<DataTableColumns[]>([])

const getData = () => {
  if (state.status?.status === 'completed') {
    axios.get(
      `${APIs.results}/${state.task_id}`,
      {
        params: {
          offset: state.pagination.page,
          length: state.pagination.length,
          order_by: state.pagination.order_by,
          order: state.pagination.order,
        }
      }
    ).then((response: AxiosResponse) => {
      table_data.value = response.data.data
      state.pagination.total = response.data.total
      state.pagination.length = response.data.length
      state.pagination.page = response.data.offset
    }).catch((error: AxiosError) => {
      showError(error)
    }).finally(() => {

    })
  }
}

const handleSorter = (sorter: DataTableSortState) => {
  if (state !== undefined && state.pagination !== null) {
    state.pagination.order_by = sorter['columnKey'].toString()
    state.pagination.order = sorter['order'].toString()

    getData()
  }
}


const getHeaders = () => {

  if (state === undefined) {
    return
  }

  axios.get(`${APIs.headers}/${state.task_id}`).then((response) => {
    table_headers.value = response.data
  }).catch(error => {
    showError(error)
  }).finally(() => {
    if (table_headers.value === null || table_headers.value === undefined || state === undefined ) {
      return
    }

    // set up columns
    let res: DataTableColumns[] = []
    for (let row of table_headers.value["categories"][state.status.description]) {
      row["minWidth"] = 100
      res.push(row)
    }

    for (let row of table_headers.value['headers']) {
      if (row["key"] === "indel_freq") {
        res.push({
          key: row["key"],
          title: row["title"],
          sorter: row["sorter"],
          minWidth: 50,
          defaultSortOrder: 'descend',
          fixed: "right",
          render: (row: RowData) => {
            return h(
                NPopover,
                {trigger: "hover"},
                {
                  trigger: () => {
                    return h(
                      NTag,
                        {bordered: false, type: "info"},
                        {default: () => row.indel_freq.toPrecision(3)}
                    )
                  },
                  default: () => row.indel_freq
                }
            )
          }
        })
      } else if (row["key"] === "target" || row["key"] === "sgrna") {
        res.push({
          key: row["key"],
          title: row["title"],
          sorter: row["sorter"],
          minWidth: "100px",
        })
      } else {
        row["minWidth"] = 90
        res.push(row)
      }
    }
    headers.value = res;

    // get first results
    getData()
  })
}


onMounted(() => {getHeaders()})


</script>

<template>
  <n-flex justify="space-around" style="margin-right: 10px">
      <n-data-table v-if="headers.length > 0"
        striped bordered
        :columns="headers" :data="table_data"
        @update:sorter="handleSorter"
      />
  </n-flex>

  <n-divider />

  <n-flex justify="center">
    <n-pagination v-if="state !== undefined && state.pagination !== null"
                  v-model:page="state.pagination.page"
                  :page-sizes="[10, 20, 30, 40]"
                  :item-count="state.pagination.total"
                  v-model:page-size="state.pagination.length"
                  @update-page="getData"
                  @update-page-size="getData"
                  show-quick-jumper show-size-picker />
  </n-flex>
</template>

<style scoped>

</style>