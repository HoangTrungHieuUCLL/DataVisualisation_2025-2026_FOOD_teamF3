import pandas as pd
import numpy as np
import unicodedata
import re
import string
import nltk
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from gensim.parsing.preprocessing import remove_stopwords # While imported in your original code, it's not used. We will stick to your custom logic.

# Ensure NLTK resources are available (needed for word_tokenize and PorterStemmer)
try:
    nltk.data.find('tokenizers/punkt')
except nltk.downloader.DownloadError:
    print("NLTK 'punkt' resource not found. Downloading...")
    nltk.download('punkt')
except:
    pass # Handle other potential import errors silently


# --- 1. Helper Functions ---

# Small list of common Dutch conjunctions/prepositions/articles to remove (from your original code)
_dutch_stopwords = {
    "met", "en", "in", "van", "op", "voor", "bij", "uit", "door",
    "naar", "om", "te", "de", "het", "een", "als", "maar", "of",
    "ook", "dan", "tot", "over"
}
_stopwords_pattern = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in _dutch_stopwords) + r")\b", flags=re.IGNORECASE)

# Initializing stemmer once for efficiency
_porter_stemmer = PorterStemmer()

def _remove_specific_chars_keep_spaces(s: str) -> str:
    """Removes specific punctuation/symbols and collapses whitespace."""
    if not isinstance(s, str):
        return s
    # 1. Replace listed characters with a single space
    s = re.sub(r"[()=&%+\;/.\u00B0-]+", " ", s)
    # 2. Remove English/apostrophe possessive forms and typographic variants
    s = s.replace("'s", " ").replace("’s", " ")
    # 3. Remove possessive forms from Dutch words (e.g., 'n)
    s = re.sub(r"(?:'n|’n)\b", " ", s)
    # 4. Also remove isolated trailing apostrophe if any
    s = re.sub(r"['’]\b", " ", s)
    # 5. Remove common Dutch stopwords (as whole words)
    s = _stopwords_pattern.sub(" ", s)
    # 6. Collapse whitespace and strip
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def _dedupe_words(text: str) -> str:
    """Removes duplicate words within a cell based on normalized key, preserving first occurrence order."""
    if not isinstance(text, str):
        return str(text) # Handle non-string input by converting
    
    tokens = text.split()
    seen = set()
    out = []
    
    for t in tokens:
        # Normalize to ASCII (remove accents), lowercase, and strip non-alphanumerics for comparison key
        key = unicodedata.normalize('NFKD', t)
        key = key.encode('ascii', 'ignore').decode('ascii')
        key = key.lower()
        key = re.sub(r'[^a-z0-9]+', '', key)
        
        # Fallback if normalization removed everything (should be rare after initial cleaning)
        if not key:
            key = t.lower()
            
        if key not in seen:
            seen.add(key)
            out.append(t)
            
    return ' '.join(out)

def _stem_sentence(sentence: str) -> str:
    """Stems words in a sentence using PorterStemmer."""
    if not isinstance(sentence, str):
        return ''
    # Use NLTK word_tokenize and the pre-initialized stemmer
    token_words = word_tokenize(sentence)
    stem_sentence = [_porter_stemmer.stem(word) for word in token_words]
    return ' '.join(stem_sentence)

def _remove_one_letter_words(text: str) -> str:
    """Removes all words with a length of exactly one character."""
    if not isinstance(text, str):
        return str(text)
    tokens = text.split()
    tokens = [t for t in tokens if len(t) > 1]
    return ' '.join(tokens)


# --- 2. Main Refactored Function ---

def create_cleaned_text_feature(df: pd.DataFrame, text_cols: list) -> pd.DataFrame:
    """
    Combines all text preprocessing steps from the original pipeline into one function,
    adds the result to a new 'to_vectorize' column, and returns the updated DataFrame.
    
    The steps include:
    1. Concatenation and basic cleanup.
    2. Lowercasing and removing numbers/commas.
    3. Removing specific punctuation and Dutch common words.
    4. Deduplicating words.
    5. Stemming words.
    6. Removing one-letter words.

    Args:
        df: The input DataFrame containing the raw product data.
        text_cols: List of column names to concatenate and process.

    Returns:
        The input DataFrame with a new column 'to_vectorize' containing the 
        final, cleaned, and stemmed text feature.
    """
    
    # Create a copy of the input DataFrame to ensure functional programming principles 
    # and avoid SettingWithCopyWarning if the input df is a view.
    df_out = df.copy()
    
    # --- Step 1 & 2: Initial Concatenation, Cleanup, Lowercasing, and removing numbers ---
    
    # Concat and basic cleanup (equivalent to concat_text and first part of concat_text_2)
    # .fillna('') must come first to allow .astype(str) to work uniformly
    text_series = (
        df_out[text_cols]
        .fillna('')                 # replace NaN with empty string
        .astype(str)                # ensure all values are strings
        .agg(' '.join, axis=1)      # join columns with spaces
    )
    
    # Lowercase, remove numbers/commas (rest of concat_text_2)
    text_series = (
        text_series
        .str.lower()
        .str.replace(r'[,\d]+', '', regex=True)  # remove commas and all numeric characters
        .str.replace(r'\s+', ' ', regex=True)    # collapse multiple spaces
        .str.strip()
    )
    
    # --- Step 3 & 4: Deduplicate and Remove specific chars/stopwords ---
    
    # 3a. Remove specific chars and Dutch stopwords (remove_specific_chars_keep_spaces logic)
    text_series = text_series.apply(_remove_specific_chars_keep_spaces)
    
    # 3b. Apply deduplication (first dedupe, original concat_text_3)
    text_series = text_series.apply(_dedupe_words)

    # --- Step 5: Stemming ---
    
    # Apply stemming (stemSentence logic, originally concat_text_5)
    text_series = text_series.apply(_stem_sentence)
    
    # Apply deduplication again after stemming (second dedupe, original concat_text_5 end)
    text_series = text_series.apply(_dedupe_words)
    
    # --- Step 6: Final cleanup (Remove one-letter words) ---
    
    # Remove one-letter words (concat_text_7)
    text_series = text_series.apply(_remove_one_letter_words)

    # Final deduplication (concat_text_7 end)
    text_series = text_series.apply(_dedupe_words)
    
    # Assign the resulting series to the new column 'to_vectorize'
    df_out['to_vectorize'] = text_series
    
    # Return the updated DataFrame
    return df_out