## APPENDIX  
FRANCESCO ESPOSITO & MARTINA D’ANTONI

## Inner functioning of LLMs

Unlike the rest of this book, which covers the use of LLMs, this appendix takes a step sideways, examining the internal, mathematical, and engineering aspects of recent LLMs (at least at a high level). It does not delve into the technical details of proprietary models like GPT-3.5 or 4, as they have not been released. Instead, it focuses on what is broadly known, relying on recent models like Llama2 and the open-source version of GPT-2. The intention is to take a behind-the-scenes look at these sophisticated models to dispel the veil of mystery surrounding their extraordinary performance.

Many of the concepts presented here originate from empirical observations and often do not (yet?) have a well-defined theoretical basis. However, this should not evoke surprise or fear. It’s a bit like the most enigmatic human organ: the brain. We know it, use it, and have empirical knowledge of it, yet we still do not have a clear idea of why it behaves the way it does.

### The role of probability

On numerous occasions, this book has emphasized that the goal of GPTs and, more generally, of LLMs trained for causal language modeling (CLM) is to generate a coherent and plausible continuation of the input text. This appendix seeks to analyze the meaning of this rather vague and nebulous statement and to highlight the key role played by probability. In fact, by definition, a language model is a probability distribution over the sequence of words (or characters or tokens), at least according to Claude E. Shannon’s definitions from 1948.

#### A heuristic approach

The concept of “reasonableness” takes on crucial importance in the scientific field, often intrinsically correlated with the concept of probability, and the case we are discussing is no exception to this rule. LLMs choose how to continue input text by evaluating the probability that a particular token is the most appropriate in the given context.

To assess how “reasonable” it is for a specific token to follow the text to be completed, it is crucial to consider the probability of its occurrence. Modern language models no longer rely on the probability of individual words appearing, but rather on the probability of sequences of tokens, initially known as n-grams. This approach allows for the capture of more complex and contextualized linguistic relationships than a mere analysis based on a single word.

##### N-grams

The probability of an n-gram’s occurrence measures the likelihood that a specific sequence of tokens is the most appropriate choice in a particular context. To calculate this probability, the LLM draws from a vast dataset of previously written texts, known as the *corpus*. In this corpus, each occurrence of token sequences (n-grams) is counted and recorded, allowing the model to establish the frequency with which certain token sequences appear in specific contexts. Once the number of n-gram occurrences is recorded, the probability of an n-gram appearing in a particular context is calculated by dividing the number of times that n-gram appears in that context by the total number of occurrences of that context in the corpus.

##### Temperature

Given the probabilities of different n-grams, how does one choose the most appropriate one to continue the input text? Instinctively, you might consider the n-gram with the highest probability of occurrence in the context of interest. However, this approach would lead to deterministic and repetitive behavior, generating the same text for the same prompt. This is where sampling comes into play. Instead of deterministically selecting the most probable token (greedy decoding, as later described), stochastic sampling is used. A word is randomly selected based on occurrence probabilities, introducing variability into the model’s generated responses.

A crucial parameter in this sampling process for LLMs is temperature. *Temperature* is a parameter used during the text-generation process to control the randomness of the model’s predictions. Just as temperature in physics regulates thermal agitation characterized by random particle motion, temperature in LLMs regulates the model’s randomness in decision-making. The choice of the temperature value is not guided by precise theoretical foundations but rather by experience. Mathematically, temperature is associated with the softmax function, which converts the last layer of a predictive neural network into probabilities, transforming a vector of real numbers into a probability vector (that is, positive numbers that sum to 1).

The definition for the softmax function on a real-number vector *z* with elements *zi* is as follows:

Softmax(z)i=eziTΣjezjT

where *T* is the temperature.

When the temperature *T* is high (for example, > 1), the softmax function amplifies differences between probabilities, making choices with already high probabilities more likely and reducing the impact of probability differences. Conversely, when the temperature is low (for example, < 1), the softmax function makes probability differences more distinct, leading to a more deterministic selection of subsequent words. Some LLMs make the sampling process deterministic by allowing the use of a seed, similar to generating random numbers in C# or Python.

##### More advanced approaches

Initially, in the 1960s, the approach to assessing “reasonableness” was as follows: Tables were constructed for each language with the probability of occurrence of every 2, 3, or 4-gram. The actual calculation of all possible probabilities of n-grams quickly becomes impractical, however. This is because n (the length of the considered sequences) increases due to the exponential number of possible combinations and the lack of a sufficiently large text corpus to cover all possible n-gram combinations. To give an idea of the magnitudes involved, consider a vocabulary of 40 thousand words; the number of possible 2-grams is 1.6 billion, and the number of possible 3-grams is 60 trillion. The number of possible combinations for a text fragment of 20 words is therefore impossible to calculate.

Recognizing the impossibility of proceeding in this direction, as often happens in science, it is necessary to resort to the use of a model. In general, models in the scientific field allow for the prediction of a result without the need for a specific quantitative measurement. In the case of LLMs, the model enables us to consider the probabilities of n-grams even without reference texts containing the sequence of interest. Essentially, we use neural networks as estimators of these probabilities. At a very high level, this is what an LLM does: It estimates, based on training data, the probability of n-grams, and then, given an input, returns the probabilities of various possible n-grams in the output, somehow choosing one.

However, as you will see, the need to use a model—and therefore an estimate—introduces limitations. These limitations, theoretically speaking, would be mitigated if it were possible to calculate the probability of occurrence for all possible n-grams with a sufficiently large n. Even in this case, there would naturally be problems: Our language is more complex, based on reasoning and free will, and it is not always certain that the word that follows in our speech is the most “probable” one, as we might simply want to say something different.

#### Artificial neurons

As mentioned, in the scientific field, it is common to resort to predictive models to estimate results without conducting direct measurements. The choice of the model is not based on rigorous theories but rather on the analysis of available data and empirical observation.

Once the most suitable model for a given problem is selected, it becomes essential to determine the values to assign to the model’s parameters to improve its ability to approximate the desired solution. In the context of LLMs, a model is considered effective when it can generate output texts that closely resemble those produced by a human, thus being evaluated “by hand.”

This section focuses on the analogies between the functioning of LLMs and that of the human brain and examines the process of selecting and adjusting the parameters of the most commonly used model through the training process.

##### Artificial neurons versus human neurons

Neural networks constitute the predominant model for natural language generation and processing. Inspired by the biology of the human brain, these networks attempt to re-create the complex exchange of information that occurs among biological neurons using layers of digital neurons. Each digital neuron can receive one or more inputs from surrounding neurons (or from the external environment, in the case of the first layer of neurons in the neural network), similar to how a biological neuron can receive one or more signals from surrounding neurons (or from sensory neurons in the case of biological neurons). While the input in biological neurons is an ionic current, in digital neurons, the input is always represented by a numerical matrix.

Regardless of the specific task the neural network is assigned (such as image classification or text processing), it is essential that the data to be processed is represented in numerical form. This representation occurs in two stages: initially, the text is mapped into a list of numbers representing the IDs of reference words (tokens), and then an actual transformation, called *embedding*, is applied. The embedding process provides a numerical representation for the data based on the principle that similar data should be represented by geometrically close vectors.

When dealing with natural language, for example, the text-embedding process involves breaking down the text into segments and creating a matrix representation of these segments. The vector of numbers generated by the embedding process can be considered as the coordinates of a point within the language feature space. The key to understanding the information contained in the text lies not so much in the individual vector representation but rather in measuring the distance between two vector representations. This distance provides information about the similarity of two text segments—crucial for completing text provided as input.

Back to the general case, upon receiving matrix inputs, the digital neuron performs two operations, one linear and one nonlinear. Consider a generic neuron in the network with N inputs:

X={x1,x2,x3⋅⋅⋅xN}(1)

Each input will reach the neuron through a “weighted” connection with weight wi. The neuron will perform a linear combination of the N inputs xi through the K weights wij (with i being the index of the neuron from which the input originates and j being the index of the destination neuron):

W⋅K+b(2)

To this linear combination, the neuron then applies a typically nonlinear function called the activation function:

f(W⋅K+b)(3)

So, for the neural network in [Figure A-1](app.xhtml#chappa_01), the output of the highlighted neuron would be:

w12f(x1w1+b1)+w22f(x2w2+b2)

![A diagram showing the structure of a neural network with interconnected nodes and layers. A highlighted node is reached by two archs, labeled as W12 and W22.](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/appa01.jpg)

***FIGURE A-1** A neural network.*

The activation function is typically the same for all neurons in the same neural network. This function is crucial for introducing nonlinearity into the network’s operations, allowing it to capture complex relationships in data and model the nonlinear behavior of natural languages. Some of the most used activation functions are ReLu, tanh, sigmoid, mish, and swish.

Once again, a parallel can be drawn with what happens inside the soma of biological neurons: After receiving electrical stimuli through synapses, spatial and temporal summation of the received signals takes place inside the soma, resulting in a typically nonlinear behavior.

The output of the digital neuron is passed to the next layer of the network in a process known as a *forward pass*. The next layer continues to process the previously generated output and, through the same processing mechanism mentioned earlier, produces a new output to pass to the next layer if necessary. Alternatively, the output of a digital neuron can be taken as the final output of the neural network, similar to the human neural interaction when the message is destined for the motor neurons of the muscle tissue.

The architectures of modern neural networks, while based on this principle, are naturally more elaborate. As an example, convolutional neural networks (CNNs) and recurrent neural networks (RNNs) use specialized structural elements. CNNs are designed to process data with spatial structure, such as images. They introduce convolutional layers that identify local patterns. In contrast, RNNs are suitable for sequential data, like language. RNNs use internal memory to process previous information in the current context, making them useful for tasks such as natural language recognition and automatic translation.

Although the ability of neural networks to convincingly emulate human behavior is not yet fully understood, examining the outputs of the early layers of the neural network in an image classification context reveals signals suggesting behavior analogous to the initial stage of neural processing of visual data.

##### Training strategies

The previous section noted that the input to a digital neuron consists of a weighted linear combination of signals received from the previous layer of neurons. However, what remains to be clarified is how the weights are determined. This task is entrusted to the training of neural networks, generally conducted through an implementation of the backpropagation algorithm.

A neural network learns “by example.” Then, based on what it has learned, it generalizes. The training phase involves providing the neural network with a typically large number of examples and allowing it to learn by adjusting the weights of the linear combination so that the output is as close as possible to what one would expect from a human.

At each iteration of the training, and therefore each time an example is presented to the neural network, a loss function is calculated backward from the obtained output (hence the name *backpropagation*). The goal is to minimize the loss function. The choice of this function is one of the degrees of freedom in the training phase, but conceptually, it always represents the distance between what has been achieved and what was intended to be achieved. Some examples of commonly used loss functions include cross-entropy loss and mean squared error (MSE).

###### Cross-entropy loss

Cross-entropy loss is a commonly used loss function in classification and text generation problems. Minimizing this error function is the goal during training. In text generation, the problem can be viewed as a form of classification, attempting to predict the probability of each token in the dictionary as the next token. This concept is analogous to a traditional classification problem where the neural network’s output is a list associating the probability that the input belongs to each possible category.

Cross-entropy loss measures the discrepancy between the predicted and actual probability distributions. In the context of a classification problem, the cross-entropy loss formula on dataset X is expressed as follows:

CEL(X,T,P)=−ΣxΣi=1Nti*log⁡(p(xi))

This formula represents the sum of the product between the actual probability and the negative logarithm of the predicted probability, summed over all elements of the training dataset X.

In particular, *ti* represents the probability associated with the actual class i (out of a total of N possible classes, where N is the size of the vocabulary in a text generation problem) and is a binary variable: It takes the value 1 if the element belongs to class i, and 0 otherwise. In contrast, *p*(*x*)*i* is the probability predicted by the neural network that the element x belongs to class i.

The use of logarithms in the cross-entropy loss function stems from the need to penalize discrepancies in predictions more significantly when the actual probability is close to zero. In other words, when the model incorrectly predicts a class with a very low probability compared to the actual class, the use of logarithm amplifies the error. This is the most commonly used error function for LLMs.

###### Mean squared error (MSE)

Mean squared error (MSE) is a commonly used loss metric in regression problems, where the goal is to predict a numerical value rather than a class. However, if applied to classification problems, MSE measures the discrepancy between predicted and actual values, assigning a quadratic weight to errors. In a classification context, the neural network’s output will be a continuous series of values representing the probabilities associated with each class.

While cross-entropy loss focuses on discrete classification, MSE extends to classification problems by treating probabilities as continuous values. The MSE formula is given by the sum of the squares of the differences between actual and predicted probabilities for each class:

MSE(X,T,P)=1|x|ΣxΣi=1N(ti−⁡(p(xi))2

Here, *ti* represents the probability associated with the actual class i (out of a total of N possible classes, where N is the size of the vocabulary in a text-generation problem) and is a binary variable that takes the value 1 if the element belongs to class i, and 0 otherwise. Meanwhile, *p*(*x*)*i* is the probability predicted by the neural network that the element x belongs to class i.

###### Perplexity loss

Another metric is *perplexity loss*, which measures how confused or “perplexed” a language model is during the prediction of a sequence of words. In general, one aims for low perplexity loss, as this indicates that the model can predict words consistently with less uncertainty:

PL(X,P)=Σxe1NΣi=1N−log⁡(p(x)i)

This is used for validation after training and not as a loss function during training; the formula does not include the actual value to be predicted, and therefore it cannot be optimized. It differs from cross-entropy loss and MSE in the way it is calculated. While cross-entropy loss measures the discrepancy between predicted and actual probability distributions, perplexity loss provides a more intuitive measure of model complexity, representing the average number of possible choices for predicting words. In short, perplexity loss is a useful metric for assessing the consistency of an LLM’s predictions, offering an indication of how “perplexed” the model is during text generation.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

As with other ML models, after training, it is customary to perform a validation phase with data not present in the training dataset, and finally, various tests with human evaluators. The human evaluators will employ different evaluation criteria, such as coherence, fluency, correctness, and so on.

##### Optimization algorithms

The goal of training is to adjust the weights to minimize the loss function. Numerical methods provide various approaches to minimize the loss function.

The most commonly used method is gradient descent: Weights are initialized, the gradient of the cost function with respect to the chosen weights is calculated, and the weights are updated using the following formula:

Wj+1=Wj+a∇J(wj)

with j being the current iteration, j + 1 being the next iteration, and a learning rate.

The process continues iteratively until reaching a pre-established stopping criterion, which can be either the number of iterations or a predefined threshold value.

Because the loss function may not necessarily have a unique absolute minimum and could also exhibit local minima, minimization algorithms may converge toward a local minimum rather than the global minimum. In the case of the gradient descent method, the choice of the learning rate α plays a crucial role in the algorithm’s convergence. Generally, convergence to the absolute minimum can also be influenced by the network’s complexity—that is, the number of layers and neurons per layer. Typically, the greater the number of layers in the network, the more weights can be adjusted, resulting in better approximation and a lower risk of reaching a local minimum.

However, there are no theoretical rules to follow regarding the learning rate in the gradient descent method and the structure to give to the neural network. The optimal structure for performing the task of interest is a matter of experimentation and experience.

As an example derived from experience, for image classification tasks, it has been observed that a first layer composed of two neurons is a particularly convenient choice. Also, from empirical observations, it has emerged that, at times, it is possible, with the same outcome, to reduce the size of the network by creating a bottleneck with fewer neurons in an intermediate layer.

There are various specific implementations of the classical gradient descent algorithm and various optimizations, including Adam; among the most widely used, it adapts the learning rate based on the history of gradients for each parameter. There are also several alternative methods to gradient descent. For example, the Newton-Raphson algorithm is a second-order optimization, considering the curvature of the loss function. Other approaches, although less commonly used, are still valid, such as genetic algorithms (inspired by biological evolution) and simulated annealing algorithms (modeled on the metal-annealing process).

##### Training objectives

Loss functions should be considered and integrated into the broader concept of the training objective—that is, the specific task you want to achieve through the training phase.

In some cases, such as for BERT, the goal is only to build an embedded representation of the input. Often, the masked language modeling (MLM) approach is adopted. Here, a random portion of the input tokens is masked or removed, and the model is tasked with predicting the masked tokens based on the surrounding context (both to the right and left). This technique promotes a deep understanding of contextual relationships in both directions, contributing to the capture of bidirectional information flow. In this case, the loss function is calculated using cross-entropy loss applied to the token predicted by the model and the originally masked one.

Other strategies, like span corruption and reconstruction, introduce controlled corruptions to the input data, training the model to reconstruct the entire original sequence. The main goal of this approach is to implicitly teach the model to understand context and generate richer linguistic representations. To guess missing words or reconstruct incorrect sequences, the model must necessarily deeply comprehend the input.

In models that aim directly at text generation, such as GPT, an autoregressive approach is often adopted, particularly CLM. With this approach, the model generates the sequence of tokens progressively, capturing sequential dependencies in the data and implicitly developing an understanding of linguistic patterns, grammatical structures, and semantic relationships. This contrasts with the bidirectional approach, where the model can consider information both to the left and right in the sequence. During training with CLM, for example, if the sequence is “The sun rises in the east”, the model must learn to predict the next word, such as “east,” based on “The sun rises in the”. This approach can naturally evolve in a self-supervised manner since any text can be used automatically to train the model without further labeling. This makes it relatively easy to find data for the training phase because any meaningful sentence is usable.

In this context, loss functions are one of the final layers of abstraction in training. Once the objective is chosen, a loss function that measures it is selected, and the training begins.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

As clarified in [Chapter 1](ch01.xhtml#ch01), in the context of LLMs, this training phase is usually called *pre-training* and is the first step of a longer process that also involves a supervised fine-tuning phase and a reinforced learning step.

##### Training limits

As the number of layers increases, neural networks acquire the ability to tackle increasingly challenging tasks and model complex relationships in data. In a sense, they gain the ability to generalize, even with a certain degree of “memory.” The universal approximation theorem even goes as far as to claim that any function can be approximated arbitrarily well, at least in a region of space, by a neural network with a sufficiently large number of neurons.

It might seem that neural networks, as “approximators,” can do anything. However, this is not the case. In nature, including human nature, there is something more; there are tasks that are *irreducible*. First, models can suffer from *overfitting*, meaning they can adapt excessively to specific training data, compromising their generalization capacity. Additionally, the inherent complexity and ambiguity of natural language can make it challenging for LLMs to consistently generate correct and unambiguous interpretations. In fact, some sentences are ambiguous and subject to interpretation even for us humans, and this represents an insurmountable limit for any model.

Despite the ability to produce coherent text, these models may lack true conceptual understanding and do not possess awareness, intentionality, or a universal understanding of the world. While they develop some map—even physical (as embeddings of places in the world that are close to each other)—of the surrounding world, they lack an explicit ontology of the world. They work to predict the next word based on a statistical model but do not have any explicit knowledge graph, as humans learn to develop from early years of life.

From a more philosophical standpoint, one must ask what a precise definition of ontology is. Is answering a question well sufficient? Probably not, if you do not fully grasp its meaning and do not reason. But what does it mean to grasp the meaning and reason? Reasoning is not necessarily making inferences correctly. And what does it mean to learn, both from a mathematical view and from a more general perspective? From a mathematical point of view, for these models, *learning* means compressing data by exploiting the regularities present, but there is still a limit imposed by Claude Shannon’s Source Code Theorem. And what does learning mean from a more general perspective? When is something considered learned?

One thing is certain: Current LLMs lack the capacity for planning. While they think about the next token during generation, we humans, when we speak, think about the next concept and the next idea to express. In fact, major research labs worldwide are working on systems that integrate LLMs as engines of more complex agents that know how to program actions and strategies first, thinking about concepts before tokens. This will likely emerge through new reinforced learning algorithms.

In conclusion, the use and development of LLMs raise deep questions about the nature of language, knowledge, ethics, and truth, sparking philosophical and ethical debates in the scientific community and beyond. Consider the concept of objective truth, and how it is fundamentally impossible for a model to be objective because LLMs learn from subjective data and reflect cultural perspectives.

### The case of GPT

This section focuses on the structure and training of GPT. Based on publicly available information, GPT is currently a neural network with (at least) 175 billion parameters and is particularly well-suited for handling language thanks to its architecture: the *transformer*.

#### Transformer and attention

Recall that the task of GPT is to reasonably continue input text based on billions of texts studied during the training phase. Let’s delve into the structure of GPT to understand how it manages to provide results very close to those that a human being would produce.

The operating process of GPT can be divided into three key phases:

1. **Creation of embedding vectors** GPT converts the input text into a list of tokens (with a dictionary of approximately 50,000 total possible tokens) and then into an embedding vector, which numerically represents the text’s features.
2. **Manipulation of embedding vectors** The embedding vector is manipulated to obtain a new vector that contains more complex information.
3. **Probability generation** GPT calculates the probability that each of the 50,000 possible tokens is the “right” one to generate given the input.

All this is repeated in an autoregressive manner, inputting the newly generated token until a special token called an end-of-sequence (EOS) token is generated, indicating the end of the generation.

Each of these operations is performed by a neural network. Therefore, there is nothing engineered or controlled from the outside except for the structure of the neural network. Everything else is guided by the learning process. There is no ontology or explicit information passed from the outside, nor is there a reinforcement learning system in this phase.

##### Embeddings

Given a vector of N input tokens (with N less than or equal to the context window, approximately between 4,000 and 16,000 tokens for GPT-3) within the GPT structure, it will initially encounter the embedding module.

Inside this module, the input vector of length N will traverse two parallel paths:

- **Canonical embedding** In the first path, called canonical embedding, each token is converted into a numerical vector (of size 768 for GPT-2 and 12,288 for GPT-3). This path captures the semantic relationships between words, allowing the model to interpret the meaning of each token. The traditional embedding does not include information about the position of a token in the sequence and can be used to represent words contextually, but without considering the specific order in which they appear. In this path, the weights of the embedding network are trainable.
- **Positional embedding** In the second path, called positional embedding, embedding vectors are created based on the position of the tokens. This approach enables the model to understand and capture the sequential order of words within the text. In autoregressive language models, the token sequence is crucial for generating the next text, and the order in which words appear provides important information for context and meaning. However, transformer-based models like GPT are not recurrent neural networks; rather, they treat input as a collection of tokens without an explicit representation of order. The addition of positional embedding addresses this issue by introducing information about the position of each token in the input. In this flow, there are no trainable weights; the model learns how to use the “fixed” positional embeddings created but cannot modify them.

The embedding vectors obtained from these two paths are then summed to provide the final output embedding to pass to the next step. (See [Figure A-2](app.xhtml#chappa_02).)

![Diagram of GPT-2 embedding schema: An arrow carrying input data of length n is connected to a box containing two parallel paths for embedding and position embedding. These paths are linked by two arrows, indicating that they are summed together to yield an output of dimension nx768 outside the box.](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/appa02.jpg)

***FIGURE A-2** The schema representing the embedding module of GPT-2.*

##### Positional embedding

The simplest approach for positional embeddings is to use the straightforward sequence of positions (that is, 0, 1, 2,...). However, for long sequences, this would result in excessively large indices. Moreover, normalizing values between 0 and 1 would be challenging for variable-length sequences because they would be normalized differently. This gives rise to the need for a different scheme.

Similar to traditional embeddings, the positional embedding layer generates a matrix of size N x 768 in GPT-2. Each position in this matrix is calculated such that for the n-th token, for the corresponding row n:

- The columns with even index 2i will have this value: P(n,2i)=sin⁡(n100002i768)
- The columns with odd index 2i+1 will have this value: P(n,2i+1)=cos⁡(n100002i768)

The value 10,000 is entirely arbitrary, but it is used for historical reasons, having been chosen in the original and revolutionary paper titled “Attention Is All You Need” (Vaswani et al., 2017). These formulas generate sinusoidal and cosinusoidal values assigned to each token position in the embedding.

The use of sinusoidal functions allows the model to capture periodic relationships. Furthermore, with values ranging from –1 to 1, there is no need for additional normalization. Therefore, given an input consisting of a sequence of integers representing token positions (a simple 0, 1, 2, 3...), a matrix of sinusoidal and cosinusoidal values of size Nx768 is produced.

Using an example with an embedding size of 4, the result would be the following matrix:

| Word | Position | i = 0 | i = 0 | i = 1 | i = 1 |
| --- | --- | --- | --- | --- | --- |
| I | 0 | Sin(0) = 0 | Cos(0) = 1 | Sin(0) = 0 | Cos(0) = 1 |
| am | 1 | Sin(2/1) = 0.84 | Cos(2/1) = 0.54 | Sin(2/10) = 0.10 | Cos(1/10) = 0.54 |
| Frank | 2 | Sin(3/1) = 0.91 | Cos(3/1) = -0.42 | Sin(3/10) = 0.20 | Cos(2/10) = 0.98 |

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

There is no theoretical derivation for why this is done. It is an operation guided by experience.

##### Self-attention at a glance

After passing through the embedding module, we reach the core architecture of GPT: the transformer, a sequence of multi-head attention blocks. To understand at a high level what *attention* means, consider, for example, the sentence “GPT is a language model created by OpenAI.” When considering the subject of the sentence, “GPT,” the two words closest to it are “is” and “a,” but neither provides information about the context of interest. However, “model” and “language,” although not physically close to the subject of the sentence, allow for a much better understanding of the context. A convolutional neural network, as used for processing images, would only consider the words closest in physical proximity, while a transformer, thanks to the attention mechanism, focuses on words that are closer in meaning and context.

Let’s consider the attention (or, to be precise, self-attention) mechanism in general. Because the embedding vector of a single token carries no information about the context of the sentence, you need some way to weigh the context. That’s what self-attention does.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

It’s important to distinguish between attention and self-attention. Whereas *attention* mechanisms allow models to selectively focus on different part of sequences called query, key, and value, *self-attention* refers specifically to a mechanism where the same sequence serves as the basis for computing query, key, and value components, enabling the model to capture internal relationships within the sequence itself.

Rather than considering the embedding of a single token, with self-attention you apply some manipulations:

1. The dot product of the embedding vector of a single token (multiplied by a *query* matrix called *MQ*) is considered with the embedding vectors of the other tokens in the sentence (each multiplied by a *key* matrix called *Mk*). Thus, considering a sentence composed of N tokens and focusing on the first one, its embedding vector will be scalar-multiplied by the N-1 embedding vectors of the remaining tokens in the sentence (all of size 768 in the case of GPT-2). The dot product outputs the angle between two vectors, so it can be thought of as a first form of similarity measure.
2. From the dot product of pairs of vectors, N weights are obtained (one weight is obtained scalarly multiplying the first token by itself), which are then normalized to have a unit sum via the softmax function. Each weight indicates how much, in comparison to other words in the input, the correspondent key-token provides useful context to a given query-token.
3. The obtained weights are multiplied by the initial embedding vectors of the input tokens (multiplied by a *value* matrix called *Mv*). This operation corresponds to weighting the embedding vector of the first token by the embedding vectors of the remaining N-1 tokens.

Repeating this operation for all tokens in the sentence is akin to each token being weighted and gaining context from the others. The correspondent output is then summed with the initial embedding vector and sent to a fully connected feed-forward network. A single set of matrices—one for queries, one for keys, and one for values—is shared among all tokens. The values within these matrices are those learned during the training process.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The last part, summing up the initial embedding vector with the obtained vector, is usually called a *residual connection*. That is, at the end of the block, the initial input sequence is directly summed with the output of the block and then re-normalized before being passed to the subsequent layers.

##### Self-attention in detail

To be more technical, the attention mechanism involves three main components: query (Q), key (K), and value (V). These are linear projections of the input sequence. That is, the input sequence is multiplied by the three correspondent matrices to obtain those three matrices.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

Here Q, K, and V are vectors, not matrices. This is because you are considering the flow for a single input token. If you consider all the N input tokens together in a matrix of dimensions N x 768, then Q, K, and V become N x 768 matrices. This is done to parallelize computation, taking advantage of optimized matrix multiplication algorithms.

So, with this notation, the components are as follows:

- **Query (Q)** The current position or element for which attention weights need to be computed. It is a linear projection of the input sequence, capturing the information at the current position.
- **Key (K)** The entire input sequence. This is also a linear projection of the input. It contains information from all positions in the sequence.
- **Value (V)** The content or features associated with each position in the input sequence. Like Q and K, V is obtained through a linear projection.

The attention mechanism calculates attention scores by measuring the compatibility (or similarity) between the query and the keys. These scores are then used to weight the values, creating a weighted sum. The resulting weighted sum is the attended representation, emphasizing the parts of the input sequence that are most relevant to the current position. This process is often referred to as *scaled dot-product attention* and is mathematically expressed as follows:

Attention(Q,K,V)=Softmax(QKT768)⁡V

where *T* is the transpose, and the softmaxed weights are scalarly multiplied by V.

##### Multi-head attention and other details

The attention mechanism as described previously can be considered a single “head” applied to each word in a sentence to obtain a more contextualized embedding for that word. However, to capture multiple contextualization patterns simultaneously, the process is rerun with different query, key, and value matrices, each initialized with random values. Each iteration of this process is referred to as a *transformer head*, and these heads are typically run in parallel.

The final contextualized embeddings from all heads are concatenated, forming a comprehensive embedding used for subsequent computations. The dimensions of the query, key, and value matrices are chosen such that the concatenated embeddings match the size of the original vector. This technique is widely used, with the original transformer paper employing eight heads.

To obtain even more information about the context, multiple layers of attention blocks (transformer layers) are often used in cascade. Specifically, GPT-2 contains 12 attention blocks, while GPT-3 contains 96.

After traversing all the attention blocks, the output becomes a new collection of embedding vectors. From these, more feed-forward networks can be added, with the last one used to obtain the probability list from which to determine the most appropriate token to continue the input text using softmax.

In conclusion, GPT is a feed-forward neural network (unlike typical RNNs, with which the attention mechanism was experimented on previously by Bahdanau et al., 2014). In its architecture, GPT features fully connected neural networks and more sophisticated parts where a neuron is connected only to specific neurons of the preceding and/or succeeding layer.

#### Training and emerging capabilities

Having provided an explanation in the previous section of how ChatGPT functions internally when given input text to generate a reasonable continuation, this section focuses on how the 175 billion parameters inside it were determined and, consequently, how GPT was trained.

##### Training

As mentioned, training a neural network involves presenting input data (in this case, text) and adjusting the parameters to minimize the error (loss function). To achieve the impressive results of GPT, it was necessary to feed it an enormous amount of text during training, mostly sourced from the web. (We are talking about trillions of webpages written by humans and more than 5 million digitized books.) Some of this text was shown to the neural network repeatedly, while other bits of text were presented only once.

It is not possible to know in advance how much data is needed to train a neural network or how large it should be; there are no guiding theories. However, note that the number of parameters in GPT’s architecture is of the same order of magnitude as the total number of tokens used during training (around 175 billion tokens). This suggests a kind of encoded storage of training data and low data compression.

While modern GPUs can perform a large number of operations in parallel, the weight updates must be done sequentially, batch by batch. If the number of parameters is n and the number of tokens required for training is of the same order of magnitude, the computational cost of training will be on the order of n^2, making the training of a neural network a time-consuming process. In this regard, the anatomical structure of the human brain presents a significant advantage, since, unlike modern computers, the human brain combines elements of memory and computation.

Once trained on this massive corpus of texts, GPT seemed to provide good results. However, especially with long texts, the artificiality of the generated text was still noticeable to a human. It was decided, therefore, not to limit the training to passive learning of data, but to follow this initial phase with a second phase of active learning with supervised fine-tuning, followed by an additional phase of reinforcement learning from human feedback (RLHF), as described in [Chapter 1](ch01.xhtml#ch01).

##### Decoding strategies and inference

Once you have a model trained to produce the next token in an autoregressive manner, you need to put it into production and perform inference. To do this, you must choose a decoding strategy. That is, given the probability distribution of possible output tokens, you must choose one and present the result to the user, repeating the operation until the EOS token is reached.

There are essentially three main decoding strategies for choosing a token:

- **Greedy search** This is the simplest method. It selects the token with the highest probability at each step. However, it may generate repetitive and less reasonable sequences. It might choose the most probable token at the first step, influencing the generation of subsequent tokens toward a less probable overall sequence. Better models suffer less from repetitiveness and exhibit greater coherence with greedy search.
- **Beam search** This addresses the repetitiveness problem by considering multiple hypotheses and expanding them at each step, ultimately choosing the one with the highest overall probability. Beam search will always find an output sequence with a higher probability than greedy search, but it is not guaranteed to find the most probable output because the number of hypotheses it considers is limited. It may still suffer from repetitions, and n-gram penalties can be introduced, punishing the repetition of n consecutive tokens.
- **Sampling** This introduces randomness into the generation process by probabilistically selecting the next word based on its conditional probability distribution. It increases diversity but may produce inconsistent outputs. There are two sub-variants to improve coherence:
  - **Top-K sampling** Filters the K most probable words, redistributing the probability mass among them. This helps avoid low-probability words but may limit creativity.
  - **Top-p (nucleus) sampling** Dynamically selects words based on a cumulative probability threshold. This allows greater flexibility in the size of the word set.

![image](/api/v2/epubs/urn:orm:book:9780138280383/files/graphics/note.jpg) Note

The EOS token indicates the end of a sequence during both the encoding and decoding phases. During encoding, it is treated like any other token and is embedded into the vector space along with other tokens. In decoding, it serves as a stopping condition, signaling the model to cease generating further tokens and indicating the completion of the sequence.

In conclusion, decoding strategies significantly influence the quality and coherence of the generated text. GPT uses the sampling method, introducing randomness into the generation process and diversifying the model’s outputs. The sampling technique allows GPT to produce more varied and creative texts than more deterministic methodologies like greedy search and beam search.

##### Emerging capabilities

You might think that to teach a neural network something new, it would be necessary to train it again. However, this does not seem to be the case. On the contrary, once the network is trained, it is often sufficient to provide it with a prompt to generate a reasonable continuation of the input text. One can offer an intuitive explanation of this without dwelling on the actual meaning of the tokens provided during training but by considering training as a phase in which the model extrapolates information about linguistic structures and arranges them in a language space. From this perspective, when a new prompt is given to an already trained network, the network only needs to trace trajectories within the language space, and it requires no further training.

Keep in mind, however, that satisfactory results can be achieved only if one stays within the scope of “tractable” problems. As soon as issues arise for which it is not possible to extract recurring structures to learn on the fly, and to which one can refer to generate a response similar to a human, it becomes necessary to resort to external computational tools that are not trained. A classic example is the result of mathematical operations: An LLM may make mistakes because it doesn’t truly know how to calculate, and instead looks for the most plausible tokens among all possible tokens.
