// Script de demostración para consultar Ollama localmente desde JavaScript / Node
const PROMPT = process.argv.slice(2).join(" ") || "Explica en 2 oraciones qué es la computación cuántica.";

async function consultarGemmaLocal() {
  console.log(`🤖 Enviando consulta a tu RTX 4060 local (Ollama)...`);
  console.log(`💬 Pregunta: "${PROMPT}"\n`);

  const startTime = Date.now();

  try {
    const response = await fetch("http://127.0.0.1:11434/api/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "qwen3.5:9b",
        prompt: PROMPT,
        stream: false
      })
    });

    const data = await response.json();
    const elapsedSec = ((Date.now() - startTime) / 1000).toFixed(2);
    const tps = (data.eval_count / (data.eval_duration / 1e9)).toFixed(1);

    console.log("--------------------------------------------------");
    console.log("📝 Respuesta de tu modelo local:");
    console.log(data.response.trim());
    console.log("--------------------------------------------------");
    console.log(`⚡ Rendimiento: ${tps} tokens/seg | ⏱️ Tiempo: ${elapsedSec}s | 🧠 Tokens: ${data.eval_count}\n`);
  } catch (error) {
    console.error("❌ Error al conectar con Ollama:", error.message);
  }
}

consultarGemmaLocal();
