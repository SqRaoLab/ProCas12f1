<script setup lang="ts">
import {BASE_URL} from "../utils.ts";

const home = `${BASE_URL}/home.png`

</script>

<template>
  <n-grid x-gap="10" y-gap=10 cols="2">
    <n-gi span="2">
      <n-card embedded hoverable>
        <n-h4>
          Our platform offers
          <n-text strong>Cas9 sgRNA efficiency prediction</n-text>
          and
          <n-text strong>comprehensive off-target analysis</n-text>
          powered by <n-a type="info" href="https://github.com/snugel/cas-offinder">Cas-OFFinder</n-a>
          —helping you design precise and reliable genome editing experiments.
        </n-h4>
      </n-card>
    </n-gi>

    <n-gi span="1">
      <n-card title="Introduction" hoverable>
        <n-blockquote align-text size="10">
          Recently, a diverse array of compact Cas effectors has been identified and explored for their potential in genome editing in mammalian cells.
            However, their widespread adoptions in both biological and translational research have been dampened due to their substantially variable and generally modest activities.
            Here, we conducted a high-throughput evaluation of the editing activities,
            PAM compatibilities and target specificities of five compact type V-F Cas12f nucleases across tens of thousands of target sequences within human cells.
            Leveraging this extensive dataset,
            we developed deep-learning algorithms (ProCas12f) capable of accurately predicting the performance of these miniature Cas12f1 nucleases,
            thus streamlining the selection of highly efficient sgRNAs at any given genomic locus. In addition, we highlight the pivotal role of sgRNA structural integrity in dictating the genome-editing efficiency of Cas12f1 nucleases, which could inform future engineering endeavors.
            Moreover, we showcased that lentiviral delivery of enOsCas12f1-sgRNA can achieve highly efficient editing at the +58 BCL11A erythroid enhancer in human CD34+ hematopoietic stem and progenitor cells (HSPCs),
            resulting in robust reactivation of fetal hemoglobin (HbF) expression. Finally, we developed eCROP-seq, a single-cell CRISPR screening approach,
            based on the enOsCas12f1 system, and conducted a pioneering proof-of-concept in vivo knockout screen in human CD34+ HSPCs,
            thus identifying novel transcription factors orchestrating hematopoiesis.
            Taken together, our findings provide valuable insights into the future optimization of Cas12f1 nucleases and underscore their potential as a versatile platform for therapeutic editing and functional genomics in primary human cells
        </n-blockquote>
      </n-card>
   </n-gi>
    <n-gi span="1">
      <n-card hoverable>
        <n-image :src="home" width="100%"/>
      </n-card>
    </n-gi>
  </n-grid>
</template>

<style scoped>
.read-the-docs {
  color: #888;
}
</style>
