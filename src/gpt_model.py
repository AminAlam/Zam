class fa_GPT():
    def __init__(self):

        import hazm
        from transformers import pipeline, AutoTokenizer, GPT2LMHeadModel

        self.tokenizer = AutoTokenizer.from_pretrained('bolbolzaban/gpt2-persian')
        self.model = GPT2LMHeadModel.from_pretrained('bolbolzaban/gpt2-persian')
        self.generator = pipeline('text-generation', self.model, tokenizer=self.tokenizer, max_length=500, config={'max_length': 500, 'temperature': 0.7, 'top_k': 50, 'top_p': 0.95, 'num_return_sequences': 4})
        self.normalizer = hazm.Normalizer()

    def generate(self, text):
        text = self.normalizer.normalize(text)
        out = self.generator(text)
        return out[0]['generated_text']
