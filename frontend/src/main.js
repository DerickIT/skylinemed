import { createApp } from 'vue'
import App from './App.vue'
import './style.css';

const app = createApp(App)

app.config.errorHandler = (err, instance, info) => {
    console.error("Global Vue Error:", err, info)
    alert(`Vue Error: ${err.message}`)
}

app.mount('#app')
