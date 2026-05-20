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

def calculate_gap(bbox1, bbox2):
    """
    Computes the minimum Euclidean distance between two bounding boxes.
    Each bbox is in the format [[x1,y1],[x2,y2],[x3,y3],[x4,y4]].
    """
    if not bbox1 or not bbox2 or len(bbox1) < 4 or len(bbox2) < 4:
        return 99999.0
        
    x_min_a, x_max_a = min(p[0] for p in bbox1), max(p[0] for p in bbox1)
    y_min_a, y_max_a = min(p[1] for p in bbox1), max(p[1] for p in bbox1)
    
    x_min_b, x_max_b = min(p[0] for p in bbox2), max(p[0] for p in bbox2)
    y_max_b = max(p[1] for p in bbox2)
    y_min_b = min(p[1] for p in bbox2)
    
    x_dist = max(0, x_min_b - x_max_a, x_min_a - x_max_b)
    y_dist = max(0, y_min_b - y_max_a, y_min_a - y_max_b)
    
    import math
    return math.sqrt(x_dist**2 + y_dist**2)

def translate_batch(texts_dict, target_language, ollama_url, ollama_model):
    """
    Translates a batch of texts with semantic block merging and color mapping using Ollama.
    texts_dict: dict of {id_str: {"text": text_str, "colors": [...], "far_from_previous": bool}}
    Returns a dict of {"results": [{"source_ids": [...], "text": translated_text, "color_spans": [...]}]}
    """
    if not texts_dict:
        return {}

    system_prompt = f"""You are a professional {target_language} native translator who needs to fluently translate text into {target_language}.

## Translation, Merging and Color Mapping Rules
1. You will receive a JSON object where the keys are IDs, and each value is an object containing:
   - "text": The text to translate.
   - "colors": A list of color groups in the original text (each has "color" hex and "words").
   - "far_from_previous": A boolean. If true, it means this text block is physically far away from the preceding text block on the screen.
2. **Semantic Block Merging**: You must analyze if adjacent text blocks are semantically connected (e.g. part of the same sentence, speech bubble, or paragraph).
   - If they are connected, you should merge them into a single coherent translated sentence.
   - **Physical Distance Constraints**: You **MUST NEVER** merge text blocks across a physical distance gap. If a block has `"far_from_previous": true`, it CANNOT be merged with the previous block.
3. For each group of merged or individual text blocks, you must output an object in the "results" list containing:
   - "source_ids": A list of integer IDs of the original text blocks that were merged to form this translation (e.g. `[0, 1]` if merged, or just `[0]` if not merged).
   - "text": The fluent translation of the merged/individual text into {target_language}.
   - "color_spans": A list mapping the exact original colors to the corresponding translated substring/span in your translation. Each item in "color_spans" must contain:
     * "color": The original color hex.
     * "span": The translated word or substring in your translation that corresponds to the original words. This "span" must be an exact substring of your translated "text".
4. Output ONLY a valid JSON object with a single root key "results" containing a list of these objects. Do not output any explanations, markdown code blocks, or additional content. Just the raw JSON.

Example Input:
{{
  "0": {{
    "text": "赤い太陽が",
    "colors": [
      {{"color": "#FF3333", "words": "赤い太陽"}}
    ],
    "far_from_previous": false
  }},
  "1": {{
    "text": "青い空に昇る",
    "colors": [
      {{"color": "#3366FF", "words": "青い空"}}
    ],
    "far_from_previous": false
  }},
  "2": {{
    "text": "別の看板",
    "colors": [
      {{"color": "#FFFFFF", "words": "別の看板"}}
    ],
    "far_from_previous": true
  }}
}}

Example Required Output Format:
{{
  "results": [
    {{
      "source_ids": [0, 1],
      "text": "The red sun rises in the blue sky",
      "color_spans": [
        {{"color": "#FF3333", "span": "The red sun"}},
        {{"color": "#3366FF", "span": "the blue sky"}}
      ]
    }},
    {{
      "source_ids": [2],
      "text": "Another sign",
      "color_spans": [
        {{"color": "#FFFFFF", "span": "Another sign"}}
      ]
    }}
  ]
}}"""

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
        content = result.get("message", {}).get("content", "{}")
        
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
    Translates all extracted text in batches, merging adjacent related boxes and fusing bboxes.
    extracted_data: list of dicts with 'id', 'text', 'word_colors', 'text_color', 'bbox'.
    Returns a unified list of merged translated items.
    """
    translated_data = []
    
    for i in range(0, len(extracted_data), batch_size):
        batch = extracted_data[i:i + batch_size]
        
        batch_to_translate = {}
        for j, item in enumerate(batch):
            far = False
            if j > 0:
                prev_item = batch[j-1]
                gap = calculate_gap(prev_item["bbox"], item["bbox"])
                h_prev = max(p[1] for p in prev_item["bbox"]) - min(p[1] for p in prev_item["bbox"])
                h_curr = max(p[1] for p in item["bbox"]) - min(p[1] for p in item["bbox"])
                threshold = max(h_prev, h_curr) * 2.5
                if gap > threshold:
                    far = True
            
            batch_to_translate[str(item["id"])] = {
                "text": item["text"],
                "colors": group_word_colors(item.get("word_colors", [])),
                "far_from_previous": far
            }
        
        translated_batch = translate_batch(batch_to_translate, target_language, ollama_url, ollama_model)
        
        results_list = []
        if isinstance(translated_batch, dict) and "results" in translated_batch:
            results_list = translated_batch["results"]
        elif isinstance(translated_batch, list):
            results_list = translated_batch
            
        translated_ids = set()
        
        if isinstance(results_list, list):
            for group in results_list:
                if not isinstance(group, dict):
                    continue
                source_ids = group.get("source_ids", [])
                
                # Resilient integer list parsing
                parsed_ids = []
                for s_id in source_ids:
                    try:
                        parsed_ids.append(int(s_id))
                    except (ValueError, TypeError):
                        pass
                        
                matching_items = [it for it in batch if it["id"] in parsed_ids and it["id"] not in translated_ids]
                if not matching_items:
                    continue
                    
                # 1. Bounding Box Fusion
                bboxes = [it["bbox"] for it in matching_items]
                x_min = min(pt[0] for bbox in bboxes for pt in bbox)
                x_max = max(pt[0] for bbox in bboxes for pt in bbox)
                y_min = min(pt[1] for bbox in bboxes for pt in bbox)
                y_max = max(pt[1] for bbox in bboxes for pt in bbox)
                merged_bbox = [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]]
                
                # 2. Extract common properties from the first block
                first_item = matching_items[0]
                bg_color = first_item.get("background_color", [255, 255, 255])
                text_color = first_item.get("text_color", [0, 0, 0])
                angle = first_item.get("angle", 0.0)
                
                translated_text = group.get("text", "").strip()
                color_spans = group.get("color_spans", [])
                
                # 3. Clean and map color spans
                valid_spans = []
                if isinstance(color_spans, list):
                    for span_obj in color_spans:
                        if isinstance(span_obj, dict) and "color" in span_obj and "span" in span_obj:
                            color = span_obj["color"]
                            span = span_obj["span"]
                            if isinstance(span, str) and span.lower() in translated_text.lower():
                                idx = translated_text.lower().find(span.lower())
                                actual_span = translated_text[idx:idx + len(span)]
                                valid_spans.append({
                                    "color": color,
                                    "span": actual_span
                                })
                                
                if not valid_spans:
                    valid_spans = [{
                        "color": rgb_to_hex(text_color),
                        "span": translated_text
                    }]
                    
                translated_data.append({
                    "id": first_item["id"],
                    "text": translated_text,
                    "bbox": merged_bbox,
                    "background_color": bg_color,
                    "text_color": text_color,
                    "angle": angle,
                    "color_spans": valid_spans
                })
                
                for it in matching_items:
                    translated_ids.add(it["id"])
                    
        # ── Resilient Fallback Loop for Skipped IDs ──
        for item in batch:
            if item["id"] not in translated_ids:
                print(f"Warning: Item {item['id']} was not processed by LLM. Running individual fallback...")
                
                fallback_dict = {
                    str(item["id"]): {
                        "text": item["text"],
                        "colors": group_word_colors(item.get("word_colors", [])),
                        "far_from_previous": False
                    }
                }
                
                fallback_res = translate_batch(fallback_dict, target_language, ollama_url, ollama_model)
                
                fallback_text = item["text"]
                fallback_spans = []
                
                res_list = []
                if isinstance(fallback_res, dict) and "results" in fallback_res:
                    res_list = fallback_res["results"]
                elif isinstance(fallback_res, list):
                    res_list = fallback_res
                    
                if isinstance(res_list, list) and len(res_list) > 0 and isinstance(res_list[0], dict):
                    fallback_text = res_list[0].get("text", item["text"])
                    fallback_spans = res_list[0].get("color_spans", [])
                    
                valid_spans = []
                if isinstance(fallback_spans, list):
                    for span_obj in fallback_spans:
                        if isinstance(span_obj, dict) and "color" in span_obj and "span" in span_obj:
                            color = span_obj["color"]
                            span = span_obj["span"]
                            if isinstance(span, str) and span.lower() in fallback_text.lower():
                                idx = fallback_text.lower().find(span.lower())
                                actual_span = fallback_text[idx:idx + len(span)]
                                valid_spans.append({
                                    "color": color,
                                    "span": actual_span
                                })
                                
                if not valid_spans:
                    valid_spans = [{
                        "color": rgb_to_hex(item.get("text_color", [0, 0, 0])),
                        "span": fallback_text
                    }]
                    
                translated_data.append({
                    "id": item["id"],
                    "text": fallback_text,
                    "bbox": item["bbox"],
                    "background_color": item.get("background_color", [255, 255, 255]),
                    "text_color": item.get("text_color", [0, 0, 0]),
                    "angle": item.get("angle", 0.0),
                    "color_spans": valid_spans
                })
                translated_ids.add(item["id"])
                
    return translated_data
