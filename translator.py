import json
import requests

def translate_batch(texts_dict, target_language, ollama_url, ollama_model):
    """
    Translates a batch of texts using Ollama.
    texts_dict: dict of {id_str: text_str}
    Returns a dict of {id_str: translated_text_str}
    """
    if not texts_dict:
        return {}

    system_prompt = f"""You are a professional {target_language} native translator who needs to fluently translate text into {target_language}.

## Translation Rules
1. You will receive a JSON object where the keys are IDs and the values are the texts to translate.
2. Output ONLY a valid JSON object where the keys are the exact same IDs, and the values are the translated texts into {target_language}.
Example Required Output Format:
{{
  "0": "Translated text 1",
  "1": "Translated text 2"
}}
Do not output any explanations, markdown code blocks, or additional content. Just the raw JSON.
3. The returned translation must maintain exactly the same number of paragraphs and format as the original text.
4. The provided texts are all regions extracted from the same screen capture. Use all the texts together as context to infer the correct meaning of ambiguous words, fix any obvious OCR typos, and produce cohesive and natural translations."""

    user_content = json.dumps(texts_dict, ensure_ascii=False)

    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "stream": False,
        "format": "json" # Ollama supports JSON format enforcement for compatible models
    }

    try:
        response = requests.post(ollama_url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        content = result.get("message", {}).get("content", "[]")
        
        try:
            print(f"DEBUG RAW CONTENT: {content}")
        except UnicodeEncodeError:
            print("DEBUG RAW CONTENT: <non-ascii content>")
            
        # Sometimes models wrap JSON in markdown block even with format="json"
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
            
        translated_data = json.loads(content.strip())
        return translated_data
    except Exception as e:
        print(f"Translation error: {e}")
        try:
            print(f"Raw model output: {content}")
        except:
            pass
        # Fallback: return original texts if translation fails
        return texts_dict

def translate_texts(extracted_data, target_language, ollama_url, ollama_model, batch_size=10):
    """
    Translates all extracted text in batches.
    extracted_data: list of dicts with 'id' and 'text'.
    Returns the same list but with 'text' updated to the translation.
    """
    translated_data = []
    
    # Process in batches
    for i in range(0, len(extracted_data), batch_size):
        batch = extracted_data[i:i + batch_size]
        batch_to_translate = {str(item["id"]): item["text"] for item in batch}
        
        translated_batch = translate_batch(batch_to_translate, target_language, ollama_url, ollama_model)
        
        # Map translated texts back to the original objects
        translation_map = {}
        if isinstance(translated_batch, dict):
            for key, val in translated_batch.items():
                if isinstance(val, str):
                    translation_map[str(key)] = val
                elif isinstance(val, dict) and "text" in val:
                    # In case it wraps it like {"0": {"text": "foo"}}
                    translation_map[str(key)] = val["text"]
        
        for item in batch:
            translated_text = translation_map.get(str(item["id"]), item["text"])
            
            orig_clean = "".join(item["text"].split()).lower()
            trans_clean = "".join(translated_text.split()).lower()
            
            # If the translated text is identical to the original (e.g. it was already in target lang),
            # skip it so we don't draw an overlay box for it.
            if orig_clean != trans_clean:
                new_item = item.copy()
                new_item["text"] = translated_text
                translated_data.append(new_item)
            
    return translated_data
