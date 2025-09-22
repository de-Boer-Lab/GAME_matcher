# GAME Matcher

## Automated and Externalized Matching

The Genomic API for Model Evaluation (GAME) introduces a module called “Matcher”, which automatically maps the Evaluator’s requested cell type, measured molecule (TF binding molecule/ protein and histone markers), and species with what a Predictor can provide. The Matcher is designed to perform this task by interpreting the relationship between terms through lexical, syntactic, and semantic matching.

- **Lexical matching:** handles cases of direct string correspondence, such as finding the exact token `A549` within a more descriptive choice like `lung adenocarcinoma cell line: A549`.
- **Syntactic matching:** addresses structural variations and common abbreviations, such as `hek-293` or `SKNSH` to `HEK293` or `SK-N-SH`, respectively.
- **Semantic matching:** uses biological knowledge to connect different terms that refer to the same entity, such as mapping the description `chronic myelogenous leukemia cell line` to its canonical name, `K562`.

## Queries Using a Local Large Language Model (LLM)

The Matcher bundles the `gemma3:12b` model and all necessary Python dependencies to map fuzzy, free-text user inputs to canonical terms from a controlled vocabulary. It operates as a standalone TCP server, accepting JSON-formatted requests and returning the best-matched term.

Running Gemma 3 locally means that the model operates directly on the hardware of the system it is deployed in, ensuring data privacy, reducing reliance on external cloud APIs, and lowering operational costs, which are crucial for sensitive or high-throughput workflows. Gemma 3 is also very lightweight and efficient to run on a single GPU or TPU.
