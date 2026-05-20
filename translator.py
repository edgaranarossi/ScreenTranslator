import json
import requests

def rgb_to_hex(rgb):
    if not rgb or len(rgb) < 3:
        return "#FFFFFF"
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"

def group_word_colors(word_colors):
    """
    Groups contiguous words of the same color together.
    Returns a list of dicts: [{"color": "#RRGGBB", "words": "contiguous string"}]
    """
    if not word_colors:
        return []
    
    grouped = []
    current_color = word_colors[0]["color"]
    current_words = [word_colors[0]["word"]]
    
    for wc in word_colors[1:]:
        if wc["color"] == current_color:
            current_words.append(wc["word"])
        else:
            joined_words = "".join(current_words) if any(ord(c) > 127 for c in "".join(current_words)) else " ".join(current_words)
            grouped.append({
                "color": current_color,
                "words": joined_words.strip()
            })
            current_color = wc["color"]
            current_words = [wc["word"]]
            
    joined_words = "".join(current_words) if any(ord(c) > 127 for c in "".join(current_words)) else " ".join(current_words)
    grouped.append({
        "color": current_color,
        "words": joined_words.strip()
    })
    
    return grouped

def translate_batch(texts_dict, target_language, ollama_url, ollama_model):
    """
    Translates a batch of texts with structured color tagging using Ollama.
    texts_dict: dict of {id_str: {"text": text_str, "colors": [...]}}
    Returns a dict of {id_str: {"text": translated_text_str, "color_spans": [...]}}
    """
    if not texts_dict:
        return {}

    system_prompt = f"""You are a professional {target_language} native translator who needs to fluently translate text into {target_language}.

## Translation and Color Mapping Rules
1. You will receive a JSON object where the keys are IDs, and each value is an object containing the "text" to translate, and a "colors" list of color groups in the original text (each group has a "color" hex and the original "words" that have this color).
2. For each item, you must output a JSON object containing:
   - "text": The fluent translation of the source text into {target_language}.
   - "color_spans": A list mapping the exact original colors to the corresponding translated substring/span in your translation. Each item in "color_spans" must contain:
     * "color": The original color hex.
     * "span": The translated word or substring in your translation that corresponds to the original words. This "span" must be an exact substring of your translated "text".
3. Output ONLY a valid JSON object where the keys are the exact same IDs, and the values are the objects described above.
4. The translated text must preserve the meaning, cohesive context, and tone of the original texts (which are from the same screen capture).

Example Input:
{{
  "0": {{
    "text": "赤い太陽が青い空に昇る",
    "colors": [
      {{"color": "#FF3333", "words": "赤い太陽"}},
      {{"color": "#FFFFFF", "words": "が"}},
      {{"color": "#3366FF", "words": "青い空"}},
      {{"color": "#FFFFFF", "words": "に昇る"}}
    ]
  }}
}}

Example Required Output Format:
{{
  "0": {{
    "text": "The red sun rises in the blue sky",
    "color_spans": [
      {{"color": "#FF3333", "span": "The red sun"}},
      {{"color": "#3366FF", "span": "the blue sky"}}
    ]
  }}
}}
Do not output any explanations, markdown code blocks, or additional content. Just the raw JSON."""

    user_content = json.dumps(texts_dict, ensure_ascii=False)

    payload = {
        "model": ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ],
        "stream": False,
        "format": "json"
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
        return {}

def translate_texts(extracted_data, target_language, ollama_url, ollama_model, batch_size=10):
    """
    Translates all extracted text in batches, preserving color spans.
    extracted_data: list of dicts with 'id', 'text', 'word_colors', 'text_color'.
    Returns the same list but with 'text' and 'color_spans' updated.
    """
    translated_data = []
    
    for i in range(0, len(extracted_data), batch_size):
        batch = extracted_data[i:i + batch_size]
        
        batch_to_translate = {}
        for item in batch:
            batch_to_translate[str(item["id"])] = {
                "text": item["text"],
                "colors": group_word_colors(item.get("word_colors", []))
            }
        
        translated_batch = translate_batch(batch_to_translate, target_language, ollama_url, ollama_model)
        
        translation_map = {}
        if isinstance(translated_batch, dict):
            for key, val in translated_batch.items():
                if isinstance(val, dict):
                    translation_map[str(key)] = val
                elif isinstance(val, str):
                    translation_map[str(key)] = {"text": val, "color_spans": []}
        
        for item in batch:
            res_obj = translation_map.get(str(item["id"]), {"text": item["text"], "color_spans": []})
            translated_text = res_obj.get("text", item["text"])
            color_spans = res_obj.get("color_spans", [])
            
            orig_clean = "".join(item["text"].split()).lower()
            trans_clean = "".join(translated_text.split()).lower()
            
            if orig_clean != trans_clean:
                new_item = item.copy()
                new_item["text"] = translated_text
                
                valid_spans = []
                if isinstance(color_spans, list):
                    for span_obj in color_spans:
                        if isinstance(span_obj, dict) and "color" in span_obj and "span" in span_obj:
                            color = span_obj["color"]
                            span = span_obj["span"]
                            if isinstance(span, str) and span.lower() in translated_text.lower():
                                # Keep actual case from translated_text
                                idx = translated_text.lower().find(span.lower())
                                actual_span = translated_text[idx:idx + len(span)]
                                valid_spans.append({
                                    "color": color,
                                    "span": actual_span
                                })
                                
                if not valid_spans:
                    t_color = item.get("text_color", [255, 255, 255])
                    valid_spans = [{
                        "color": rgb_to_hex(t_color),
                        "span": translated_text
                    }]
                    
                new_item["color_spans"] = valid_spans
                translated_data.append(new_item)
            
    return translated_data
