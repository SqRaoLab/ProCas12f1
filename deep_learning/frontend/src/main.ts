import { createApp } from 'vue'
import App from './App.vue'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router';

const routes: RouteRecordRaw[] = [
    { path: '/procas12f', component:  () => import("./page/home.vue"), name: 'Home' },
    { path: '/procas12f/prediction', component: () => import("./page/predict.vue"), name: "Prediction" },
    { path: '/procas12f/results', component:  () => import("./page/results.vue"), name: "Results" },
    { path: '/procas12f/upload', component:  () => import("./page/upload.vue"), name: "Upload" },
    { path: '/procas12f/help', component:  () => import("./page/help.vue"), name: "Help" },
];

const router = createRouter({
    history: createWebHistory(),
    routes
});

createApp(App).use(router).mount('#app')