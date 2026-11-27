# contents

**[*preface*](../Text/preface.html)**

**[*acknowledgments*](../Text/acknowledgments.html)**

**[*about this book*](../Text/about-this-book.html)**

**[*about the author*](../Text/about-the-author.html)**

**[*about the cover illustration*](../Text/about-the-cover-illustration.html)**

**[*1 Understanding large language models*](../Text/chapter-1.html)**

[1.1 What is an LLM?](../Text/chapter-1.html#p12)

[1.2 Applications of LLMs](../Text/chapter-1.html#p23)

[1.3 Stages of building and using LLMs](../Text/chapter-1.html#p30)

[1.4 Introducing the transformer architecture](../Text/chapter-1.html#p43)

[1.5 Utilizing large datasets](../Text/chapter-1.html#p56)

[1.6 A closer look at the GPT architecture](../Text/chapter-1.html#p68)

[1.7 Building a large language model](../Text/chapter-1.html#p78)

**[*2 Working with text data*](../Text/chapter-2.html)**

[2.1 Understanding word embeddings](../Text/chapter-2.html#p11)

[2.2 Tokenizing text](../Text/chapter-2.html#p24)

[2.3 Converting tokens into token IDs](../Text/chapter-2.html#p63)

[2.4 Adding special context tokens](../Text/chapter-2.html#p95)

[2.5 Byte pair encoding](../Text/chapter-2.html#p130)

[2.6 Data sampling with a sliding window](../Text/chapter-2.html#p154)

[2.7 Creating token embeddings](../Text/chapter-2.html#p203)

[2.8 Encoding word positions](../Text/chapter-2.html#p230)

**[*3 Coding attention mechanisms*](../Text/chapter-3.html)**

[3.1 The problem with modeling long sequences](../Text/chapter-3.html#p12)

[3.2 Capturing data dependencies with attention mechanisms](../Text/chapter-3.html#p22)

[3.3 Attending to different parts of the input with self-attention](../Text/chapter-3.html#p30)

[3.3.1 A simple self-attention mechanism without trainable weights](../Text/chapter-3.html#p36)

[3.3.2 Computing attention weights for all input tokens](../Text/chapter-3.html#p78)

[3.4 Implementing self-attention with trainable weights](../Text/chapter-3.html#p109)

[3.4.1 Computing the attention weights step by step](../Text/chapter-3.html#p115)

[3.4.2 Implementing a compact self-attention Python class](../Text/chapter-3.html#p168)

[3.5 Hiding future words with causal attention](../Text/chapter-3.html#p193)

[3.5.1 Applying a causal attention mask](../Text/chapter-3.html#p197)

[3.5.2 Masking additional attention weights with dropout](../Text/chapter-3.html#p233)

[3.5.3 Implementing a compact causal attention class](../Text/chapter-3.html#p248)

[3.6 Extending single-head attention to multi-head attention](../Text/chapter-3.html#p264)

[3.6.1 Stacking multiple single-head attention layers](../Text/chapter-3.html#p268)

[3.6.2 Implementing multi-head attention with weight splits](../Text/chapter-3.html#p284)

**[*4 Implementing a GPT model from scratch to generate text*](../Text/chapter-4.html)**

[4.1 Coding an LLM architecture](../Text/chapter-4.html#p10)

[4.2 Normalizing activations with layer normalization](../Text/chapter-4.html#p49)

[4.3 Implementing a feed forward network with GELU activations](../Text/chapter-4.html#p90)

[4.4 Adding shortcut connections](../Text/chapter-4.html#p117)

[4.5 Connecting attention and linear layers in a transformer block](../Text/chapter-4.html#p143)

[4.6 Coding the GPT model](../Text/chapter-4.html#p161)

[4.7 Generating text](../Text/chapter-4.html#p203)

**[*5 Pretraining on unlabeled data*](../Text/chapter-5.html)**

[5.1 Evaluating generative text models](../Text/chapter-5.html#p10)

[5.1.1 Using GPT to generate text](../Text/chapter-5.html#p13)

[5.1.2 Calculating the text generation loss](../Text/chapter-5.html#p27)

[5.1.3 Calculating the training and validation set losses](../Text/chapter-5.html#p101)

[5.2 Training an LLM](../Text/chapter-5.html#p141)

[5.3 Decoding strategies to control randomness](../Text/chapter-5.html#p171)

[5.3.1 Temperature scaling](../Text/chapter-5.html#p180)

[5.3.2 Top-k sampling](../Text/chapter-5.html#p206)

[5.3.3 Modifying the text generation function](../Text/chapter-5.html#p224)

[5.4 Loading and saving model weights in PyTorch](../Text/chapter-5.html#p236)

[5.5 Loading pretrained weights from OpenAI](../Text/chapter-5.html#p252)

**[*6 Fine-tuning for classification*](../Text/chapter-6.html)**

[6.1 Different categories of fine-tuning](../Text/chapter-6.html#p10)

[6.2 Preparing the dataset](../Text/chapter-6.html#p20)

[6.3 Creating data loaders](../Text/chapter-6.html#p48)

[6.4 Initializing a model with pretrained weights](../Text/chapter-6.html#p83)

[6.5 Adding a classification head](../Text/chapter-6.html#p99)

[6.6 Calculating the classification loss and accuracy](../Text/chapter-6.html#p143)

[6.7 Fine-tuning the model on supervised data](../Text/chapter-6.html#p174)

[6.8 Using the LLM as a spam classifier](../Text/chapter-6.html#p201)

**[*7 Fine-tuning to follow instructions*](../Text/chapter-7.html)**

[7.1 Introduction to instruction fine-tuning](../Text/chapter-7.html#p11)

[7.2 Preparing a dataset for supervised instruction fine-tuning](../Text/chapter-7.html#p16)

[7.3 Organizing data into training batches](../Text/chapter-7.html#p50)

[7.4 Creating data loaders for an instruction dataset](../Text/chapter-7.html#p109)

[7.5 Loading a pretrained LLM](../Text/chapter-7.html#p127)

[7.6 Fine-tuning the LLM on instruction data](../Text/chapter-7.html#p148)

[7.7 Extracting and saving responses](../Text/chapter-7.html#p174)

[7.8 Evaluating the fine-tuned LLM](../Text/chapter-7.html#p203)

[7.9 Conclusions](../Text/chapter-7.html#p260)

[7.9.1 What’s next?](../Text/chapter-7.html#p263)

[7.9.2 Staying up to date in a fast-moving field](../Text/chapter-7.html#p266)

[7.9.3 Final words](../Text/chapter-7.html#p268)

**[*appendix A Introduction to PyTorch*](../Text/appendix-a.html)**

[A.1 What is PyTorch?](../Text/appendix-a.html#p5)

[A.1.1 The three core components of PyTorch](../Text/appendix-a.html#p8)

[A.1.2 Defining deep learning](../Text/appendix-a.html#p12)

[A.1.3 Installing PyTorch](../Text/appendix-a.html#p23)

[A.2 Understanding tensors](../Text/appendix-a.html#p58)

[A.2.1 Scalars, vectors, matrices, and tensors](../Text/appendix-a.html#p65)

[A.2.2 Tensor data types](../Text/appendix-a.html#p68)

[A.2.3 Common PyTorch tensor operations](../Text/appendix-a.html#p83)

[A.3 Seeing models as computation graphs](../Text/appendix-a.html#p115)

[A.4 Automatic differentiation made easy](../Text/appendix-a.html#p123)

[A.5 Implementing multilayer neural networks](../Text/appendix-a.html#p140)

[A.6 Setting up efficient data loaders](../Text/appendix-a.html#p191)

[A.7 A typical training loop](../Text/appendix-a.html#p224)

[A.8 Saving and loading models](../Text/appendix-a.html#p273)

[A.9 Optimizing training performance with GPUs](../Text/appendix-a.html#p281)

[A.9.1 PyTorch computations on GPU devices](../Text/appendix-a.html#p283)

[A.9.2 Single-GPU training](../Text/appendix-a.html#p303)

[A.9.3 Training with multiple GPUs](../Text/appendix-a.html#p319)

**[*appendix B References and further reading*](../Text/appendix-b.html)**

**[*appendix C Exercise solutions*](../Text/appendix-c.html)**

**[*appendix D Adding bells and whistles to the training loop*](../Text/appendix-d.html)**

[D.1 Learning rate warmup](../Text/appendix-d.html#p9)

[D.2 Cosine decay](../Text/appendix-d.html#p23)

[D.3 Gradient clipping](../Text/appendix-d.html#p32)

[D.4 The modified training function](../Text/appendix-d.html#p54)

**[*appendix E Parameter-efficient fine-tuning with LoRA*](../Text/appendix-e.html)**

[E.1 Introduction to LoRA](../Text/appendix-e.html#p3)

[E.2 Preparing the dataset](../Text/appendix-e.html#p24)

[E.3 Initializing the model](../Text/appendix-e.html#p40)

[E.4 Parameter-efficient fine-tuning with LoRA](../Text/appendix-e.html#p53)

[index](../Text/index.html)
