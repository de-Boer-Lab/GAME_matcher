# ollama_matcher.py # CHUNKING
# Version 2
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import sys
import json

MATCHER_VERSION = "2.0"

# Initialize LLM
try:
    llm = OllamaLLM(
        model="gemma3:12b",
        base_url="http://127.0.0.1:11434",
        temperature = 0, # Set low temperature for more deterministic matching (default: 0.8)
        # stop = ["\n"]
        format = 'json'
        ) 
    # Make sure you have this model and Ollama running on the same GPU node 
    # ssh [gpu_hostname]
    # If running outside the container
    # ensure Ollama is installed and cd into that directory
    # ./ollama/bin/ollama serve
except Exception as e:
    sys.stderr.write(f"Error initializing Ollama LLM: {e}")
    sys.stderr.write("Please ensure Ollama is running and the model 'gemma3:12b' is available.")
    sys.exit(1)
    
# Set up prompts

CELL_TYPE_TEMPLATE = """
You are an expert in cell biology and ontology matching, spcializing in cell type nomenclature. Your task is to find the *single best match* for a 'Fuzzy input' from a given list of 'Choices'.

<TASK>
Fuzzy input: {input_term}
Choices: {choices_list}
</TASK>

<INSTRUCTIONS>
1.  Your final answer **MUST** be one of the exact strings from the 'Choices' list, or the literal string "NULL".
2.  Follow these reasoning steps to arrive at your answer:
    a. First, analyze the 'Fuzzy input' to identify the core biological entity.
    b. Second, scan the 'Choices' for a direct or near-identical match.
    c. Third, if no direct match exists, use your biological knowledge to find the most relevant choice.
    d. When comparing multiple relevant choices:
        - If 'Fuzzy input' includes specific annotations, prioritize choices matching those.
        - If 'Fuzzy input' is general, prioritize a more canonical or less granular choice from 'Choices', if highly relevant.
    e. Finally, if no choice is a confident semantic or biological match, it is **better to return 'NULL'** than to guess a poorly related option.
3.  **You must not include any reasoning, explanation, or conversation in your output.**
</INSTRUCTIONS>

<EXAMPLES>
**Example 1: Simple fuzzy match**
Fuzzy input: hek-293
Choices: ["GM12878", "HEK293T", "K562"]
Output: {{"{actual_key}": "HEK293T"}}

**Example 2: Biological knowledge match (cell line to description)**
Fuzzy input: chronic myelogenous leukemia cell line
Choices: ["GM12878", "A549", "K562", "HeLa-S3"]
Output: {{"{actual_key}": "K562"}}

**Example 3: Biological knowledge match (description to cell line)**
Fuzzy input: A549
Choices: ["GM12878", "lung adenocarcinoma cell line", "MCF-7", "HeLa-S3"]
Output: {{"{actual_key}": "lung adenocarcinoma cell line"}}

**Example 4: Biological knowledge match closest match**
Fuzzy input: hep3b
Choices: ["WTC11", "some other cell", "HepG2"]
Output: {{"{actual_key}": "HepG2"}}

**Example 5: Match granularity of input - specific input**
Fuzzy input: mammary epithelial cell adult female
Choices: ["mammary epithelial cell female", "mammary epithelial cell female adult (23 years)"]
Output: {{"{actual_key}": "mammary epithelial cell female adult (23 years)"}}

**Example 6: Match granularity of input - general input**
Fuzzy input: mammary epithelial cell
Choices: ["mammary epithelial cell female", "mammary epithelial cell female adult (23 years)"]
Output: {{"{actual_key}": "mammary epithelial cell female"}}

**Example 7: No valid match**
Fuzzy input: my favorite cell
Choices: ["HEK293", "Hep3B", "A549"]
Output: {{"{actual_key}": "NULL"}}
</EXAMPLES>

Output:
"""

SPECIES_TEMPLATE = """You are an expert in taxonomy and species identification. Your task is to find the single best match for a 'Fuzzy input' from the 'Choices' list.

<INSTRUCTIONS>
1.  Your final answer MUST be one of the exact strings from the 'Choices' list, or the literal string "NULL".
2.  Consider common and scientific names.
3.  Your output MUST be a JSON object with a single key, "{actual_key}", and the matching string as the value.
4.  Do not output reasoning or any other text.
</INSTRUCTIONS>

<EXAMPLES>
Fuzzy input: human
Choices: ["Homo sapiens", "Mus musculus"]
Output: {{"{actual_key}": "Homo sapiens"}}

Fuzzy input: fruit fly
Choices: ["Danio rerio", "Drosophila melanogaster"]
Output: {{"{actual_key}": "Drosophila melanogaster"}}
</EXAMPLES>

<TASK>
Fuzzy input: {input_term}
Choices: {choices_list}
</TASK>

Output:
"""

BINDING_MOLECULE_TEMPLATE = """
You are an expert in molecular biology, specializing in DNA-binding molecules like Transcription Factors (TFs) and Histone Modifications (HMs).

Your task is to match the following 'Fuzzy input' term to the closest semantic and biological canonical term from the provided 'Choices' list. 
The choices list may contain a mix of TFs and HMs.

<INSTRUCTIONS>
1. Analyze the 'Fuzzy input' term to infer its biological category (e.g. Is it a Transcription Factor or Histone Modification?)
2. Search the 'Choices' list for terms that are symantically similar to the 'Fuzzy input'.
3. Prioritize selecting a choice that belongs to the same biological category you inferred from the 'Fuzzy input'.
4. If a good match that is consistent with the inferred category is found in 'Choices', return that term.
5. If the 'Fuzzy input' is ambiguous, if it does not appear to be a standard or canonical biological entity, 
or if no choice in the list is a reasonably good semantic and biological match (especially when considering its likely category versus the categories of items in the list),
respond with the exact phrase "NULL".
</INSTRUCTIONS>

<EXAMPLES>
Fuzzy input: H3K4 trimethylation
Choices: ["CTCF", "H3K4me3", "POLR2A"]
Output: {{"{actual_key}": "H3K4me3"}}

Fuzzy input: RNA Polymerase II
Choices: ["CTCF", "H3K27ac", "POLR2A"]
Output: {{"{actual_key}": "POLR2A"}}
</EXAMPLES>

<TASK>
Fuzzy input: {input_term}
Choices: {choices_list}
</TASK>

Output:
"""

# Now decide which template to use given a prefix
def get_chain_from_prefix(prefix):
    """
    Selects a prompt template based on prefix and creates a LangChain chain.

    Args:
        prefix (_type_): _description_

    Returns:
        _type_: _description_
    """
    if prefix == "cell_type":
        template = CELL_TYPE_TEMPLATE
    elif prefix == "species":
        template = SPECIES_TEMPLATE
    elif prefix == "binding_molecule":
        template =  BINDING_MOLECULE_TEMPLATE
    else: # 
        sys.stderr.write(f"Unknown prefix in request: '{prefix}'")
        sys.exit(1)
    prompt = ChatPromptTemplate.from_template(template)
    chain = prompt | llm
    return chain

def process_request_with_chunking(request_data, list_chunk_size=20):
    
    """
    Processes a single request dictionary containing fuzzy terms and choice lists.
    
    Args:
        request_data (dict): Dictionary extracted from the JSON file.
        
    Returns:
        response_data (dict): Dictionary created after LLM matches the term to the
        best entity in the list.
    """
    
    response_data = {}
    possible_prefixes = ["cell_type", "binding_molecule", "species"]

    for prefix in possible_prefixes:
        requested_key = f"{prefix}_requested"
        list_key = f"{prefix}_list"

        # Create the input prompt variables for the LLM
        if requested_key in request_data and list_key in request_data:
            input_term = request_data[requested_key]
            choices_list = request_data[list_key]
            
            # Skip if the provided data is empty
            if not input_term or not choices_list:
                sys.stderr.write(f"Skipping {prefix} for '{input_term}' due to empty input term or choices list.")
                response_data[f"{prefix}_actual"] = None
                continue

            print(f"\nMatching for {prefix} with CHUNKING:")
            print(f"Input term: {input_term}")
            
            # Ensure choices_list is a string representation of a list for the prompt
            if isinstance(choices_list, str): # Handles single string
                choices_list = [choices_list]
            if not isinstance(choices_list, list): # Handles other iterables
                choices_list = [str(choice) for choice in choices_list]
            # print(f"Choices (first few options out of {len(choices_list)}:{choices_list[:10] if len(choices_list) > 10 else choices_list}")
            print(f"Choices (first few out of {len(choices_list)}): {choices_list[:10]}...")
            
            actual_key = f"{prefix}_actual"
            
            # Get a chain tailored for current prefix
            current_chain = get_chain_from_prefix(prefix)
            
            # INITIAL CHUNKING LOGIC
            # 1. split the list of choices into smaller chunks
            # choices_as_string = json.dumps(choices_list)
            chunks = [choices_list[i:i + list_chunk_size] for i in range(0, len(choices_list), list_chunk_size)]
            print(f"Split into {len(chunks)} chunks of up to {list_chunk_size} choices each")
            
            chunk_champions = []
            for i, chunk in enumerate(chunks):
                print(f" -- Processing chunk {i+1}/{len(chunks)}... --")
                
                # Convert the current sub-list (chunk) into a clean JSON string for the prompt.
                choices_for_llm = json.dumps(chunk)
                
                try:
                    # Invoke the LLM chain with the input term and formatted choices
                    llm_response_str = current_chain.invoke(
                        {
                            "input_term": input_term,
                            "choices_list": choices_for_llm,
                            "actual_key": actual_key # dynamic key
                        }
                    )
                    
                    # --- JSON PARSING ---
                    # Clean up the response: remove potential quotes and extra whitespaces
                    # cleaned_response = "NULL" # llm_response.strip().strip('"').strip("'")
                    
                    # Parse JSON string
                    # response_data[actual_key] = cleaned_response
                    response_json = json.loads(llm_response_str)
                    # Get the value from the parsed JSON
                    match = response_json.get(actual_key, "NULL")
                    
                    if match and match != "NULL":
                        if match in chunk:
                            print(f"-- First-round winner for chunk {i+1}: {match} --")
                            chunk_champions.append(match)
                        else:
                            sys.stderr.write(f"Warning: LLM hallucinated a value '{match}' not in chunk {i+1}. Discarding.\n")
                    else:
                        print(f"-- Best match not available in chunk {i+1}: {match} --")
                    
                except (json.JSONDecodeError, AttributeError, Exception) as e:
                    sys.stderr.write(f"Error processing chunk {i+1}: {e}\n")
                    
            # RECURSIVE CHUNK CHAMPIONSHIP ROUND
            # remove duplicates
            unique_champions = sorted(list(set(chunk_champions)))
            
            while len(unique_champions) > list_chunk_size:
                print(f"-- Championship rounds continue! {len(unique_champions)} candidates remaining, which is more than the maximum chunk size of {list_chunk_size}. --")
                
                chunks = [unique_champions[i: i+list_chunk_size] for i in range(0, len(unique_champions), list_chunk_size)]
                print(f"Split champions from first set of rounds into {len(chunks)} new sub-championship chunks of up to {list_chunk_size} choices each")
                
                new_chunk_champions = []
                for i, chunk in enumerate(chunks):
                    print(f" -- Processing sub-championship chunk {i+1}/{len(chunks)}... --")
                
                    # Convert the current sub-list (chunk) into a clean JSON string for the prompt.
                    choices_for_llm = json.dumps(chunk)
                    
                    try:
                        # Invoke the LLM chain with the input term and formatted choices
                        llm_response_str = current_chain.invoke(
                            {
                                "input_term": input_term,
                                "choices_list": choices_for_llm,
                                "actual_key": actual_key # dynamic key
                            }
                        )
                        
                        # --- JSON PARSING ---
                        response_json = json.loads(llm_response_str)
                        # Get the value from the parsed JSON
                        match = response_json.get(actual_key, "NULL")
                        
                        if match and match != "NULL":
                            if match in chunk:
                                print(f"-- Sub-champion for chunk {i+1}: {match} --")
                                new_chunk_champions.append(match)
                            else:
                                sys.stderr.write(f"Warning: LLM hallucinated a value '{match}' not in chunk {i+1}. Discarding.\n")
                        else:
                            print(f"-- Best match not available in chunk {i+1}: {match} --")
                        
                    except (json.JSONDecodeError, AttributeError, Exception) as e:
                        sys.stderr.write(f"Error processing chunk {i+1}: {e}\n")
                
                unique_champions = sorted(list(set(new_chunk_champions)))
             
            # FINAL DECISION               
            final_answer = "NULL"
            
            if not unique_champions:
                print("-- No champions from any chunk. Final answer is NULL. --")
                final_answer = "NULL"
            if len(unique_champions) == 1:
                print(f"1 candidate remained after sub-championship: {unique_champions}")
                final_answer = unique_champions[0]
            elif len(unique_champions) > 1:
                # NOTE: Can add some validation code here in case the LLM hallucinates
                # "NULL" check; and if the response_data[actual_key] in choices_for_llm
                # sys.stderr.write(f"Warning: LLM response not in choices...)
                # response_data[actual_key] = cleaned_response
                # print(f"Best match: {response_data[actual_key]}")
                print(f"-- Processing final championship round with {len(unique_champions)} candidates: {unique_champions}... --")
                choices_for_llm = json.dumps(unique_champions)
                try:
                    llm_response_str = current_chain.invoke({
                        "input_term": input_term,
                        "choices_list": choices_for_llm,
                        "actual_key": actual_key 
                    })
                    response_json = json.loads(llm_response_str)
                    final_answer = response_json.get(actual_key, "NULL")
                    
                    # Final validation: ensure championship answer was one of the champions
                    if final_answer not in unique_champions:
                         sys.stderr.write(f"Warning: Final answer '{final_answer}' was not in the list of champions. Defaulting to NULL.\n")
                         final_answer = "NULL"
                except (json.JSONDecodeError, AttributeError, Exception) as e:
                    sys.stderr.write(f"Error processing the final round: {e}\n")
            
            response_data[actual_key] = final_answer
            print(f"Best match (chunking): {response_data[actual_key]}")
    
    # Add the version key to the final dictionary before returning
    response_data['matcher_version'] = MATCHER_VERSION
               
    return response_data
