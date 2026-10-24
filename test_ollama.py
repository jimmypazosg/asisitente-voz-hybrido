from asistente import consultar_ollama

pregunta = "¿Qué hora es o qué día es hoy?"
print(f"Probando consulta: '{pregunta}'")
respuesta = consultar_ollama(pregunta)
print(f"Respuesta obtenida: {respuesta}")
