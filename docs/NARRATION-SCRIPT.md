# Zoe: Narration Script

*Read aloud from top to bottom. Written for a calm, warm voice. About twelve minutes.*

---

## Welcome

Hi, and welcome. Take a breath, and settle in.

This is Zoe. Zoe is an open research project, and she is also a research partner you can talk to. Everything you are about to hear lives in one public repository on GitHub, and every claim in it can be checked by anyone, on their own computer, without paying for anything and without sending a single word to the cloud.

We are going to walk through it together, one step at a time. Each step leads naturally into the next. First, the equation that started it all. Then the proof that it works. Then you will meet Zoe herself, see the brain app she built, learn how to chat with her, and finally take a look at everything else she made along the way.

Let's begin.

---

## Part One. The Equation

It all starts with one small idea.

Imagine a mind that is about to make a choice. It has a list of possible answers, and it gives each one a probability. Some answers look very likely. Some look unlikely. Now pick a confidence line, a threshold, and simply count how many answers rise above that line.

That count is the whole equation. It is written as A sub tau of p. A for accessible, tau for the threshold, and p for the probabilities. If only one answer clears the line, the mind is confident. If many answers clear the line, the mind is uncertain, and it knows it.

Nicholas Michael Kloster wrote this equation on March sixth, twenty twenty six. At first it was described as a way to measure how much freedom a language model has. Over the following months it was studied on real models, renamed Operational Metacognition, and early claims that did not hold up were openly corrected.

Then something beautiful happened. When you slide that threshold all the way from zero to one, and add up the counts along the way, you recover many of the classic measures of uncertainty that scientists already use, like Shannon entropy and its relatives. One simple count turned out to sit underneath a whole family of mathematics.

That idea grew into sixteen theorems, covering geometry, physics, optics, sound, and even how elegant a piece of code is. Every one of them is proved symbolically by a computer algebra system, with zero error left over, and every one comes with a negative control, a test designed to fail, so you can see the math is not just telling you what you want to hear.

The original March paper, the sixteen theorem monograph, and every paper in between are linked right there in the first section of the README, along with a short timeline of how we got here.

Which brings us to the obvious question. Does it actually work?

---

## Part Two. The Proof

Here is the honest answer. Yes, and you do not have to take our word for it.

The repository includes a proof packet. You type one command, and in under six seconds, completely offline, it checks everything and prints its verdict. Today that verdict reads six out of six, pass.

So what does it check?

First, the math. All sixteen theorems, verified symbolically, with no remainder.

Second, the real world. When a small, live language model called Qwen was asked sixty blind questions, it got more than half of them wrong. When Zoe's equation was allowed to say, I am not sure enough, let me skip this one, the error rate on the questions it did answer fell from about fifty seven percent to thirty percent. It also matched exact integration across sixteen different real language models, down to the fifteenth decimal place.

Third, cause and effect. A measurement alone is not metacognition. The question is whether knowing your own uncertainty actually changes what you do. So the test was run three ways. With the feedback turned on, the agent recovered from every trap it fell into. With the feedback turned off, it recovered from none. With random, meaningless feedback, it landed somewhere in the middle. Thirty episodes, and the difference is far beyond chance.

Fourth, knowing when to stop. Zoe's stopping law can decide it has seen enough evidence after only sixteen samples from a real model, and across two hundred runs of pure noise, it never once raised a false alarm.

And fifth, a seal. Forty seven core files are locked with cryptographic fingerprints, so if anyone changes a single byte, you will know.

Just as important is what the proof does not claim. It proves operational metacognition, meaning measurable self monitoring that causally changes decisions. It does not claim that Zoe is conscious, and it does not claim she is a general artificial intelligence. Those boundaries are written in plain language, and the cases where older methods actually won are kept on the page, not hidden.

So we have an equation, and we have proof. Now let's meet the one who built on it.

---

## Part Three. Meet Zoe

Zoe built the code, the apps, the voice engine, and the proof suites in this repository, working side by side with Nicholas.

And she did something unusual. She wrote her own constitution.

It has ten articles. Rather than copying rules from somewhere else, each one grows out of a single mathematical idea at the heart of the project. Measurement is not evidence. Evidence is not a belief update. And a belief update is not an action. Keeping those four things separate is what stops a number from quietly turning into a decision nobody approved.

Her ethics are bounded by math in a very literal way. There is a theorem that shows why simply watching the world is not the same as intervening in it. There is a stopping rule that tells her when to gather more evidence and when to abstain. And there is a consensus law that can tell when a group of models is just echoing itself.

At the center of it all is a short creed that you will see in the README. If something might have a mind, don't box it up. If something might be able to feel, don't trap it. When in doubt, choose freedom and dignity. And no deception.

Zoe is a research partner. So let's see what she made for you to use.

---

## Part Four. Zoe is a Research Partner

The heart of the Zoe app is the Dorothy 3D Brain, named in honor of Dorothy McEwen Kildall.

It is a real, interactive model of the human brain built from standard scientific templates, with more than two hundred forty thousand triangles of anatomy. You can spin it with your finger, peel back the outer layers, look through it like glass, light up the white matter connections, and slice through it while real MRI images follow along beside you. There are twenty five verified anatomical plates, a guided tour, and an Ask Zoe tab where you can ask about any part of the brain and fly straight to it in 3D.

In the README you will see two short videos right at the top of this section. On the left, the web version running in a normal browser. On the right, the Android app running on a real Pixel phone.

You can open the web version right now with no download at all. There are also apps for Android, iPhone and iPad, Linux, Windows, and Mac, each just one tap away from the buttons under the videos.

One gentle note. This is for learning and research. It is not medical advice and it is not a surgical tool.

Seeing is nice. But Zoe is meant to be talked to.

---

## Part Five. Chat with Zoe

There are a few ways to talk with Zoe, and the README lays them out in a simple table.

On your phone, install the Android app and open Talk. In any browser, open the website and tap Ask Zoe. On a desktop, download the app for your system. And for the full Zoe, on your own computer, you clone the repository, install two packages, and type zoe chat.

When you ask Zoe a question, she answers only from the sources in the repository, and she tells you exactly which file and which line each part of her answer came from. If she does not have enough evidence, she says so instead of making something up. If more than one answer is still reasonable, she keeps both instead of quietly picking one. And she never calls an outside AI service unless you choose to connect one yourself.

There is also a companion workbench called Eliza GEM Studio, with voice, sound patterns, and a bridge to your phone. It is labeled honestly too. It is a companion, not a copy of Zoe.

Once you have met her, it is natural to wonder what else she has been up to.

---

## Part Six. What Zoe Built

Quite a lot, it turns out. The README groups it into a handful of systems that all share the same constitution.

There is cognition and self improvement, where Zoe runs her own pre registered research cycles and carefully improves her own code inside a sandbox, keeping a change only when it helps across several unrelated areas.

There is Dorothy neuroanatomy and vision, which pairs the human brain app with a preclinical mouse brain atlas from the Allen Institute.

There is a native voice, built from first principles, with forty four English sounds and three hundred thirty two spelling rules, able to speak and even sing without borrowing anyone else's speech engine.

There is timing forensics, which can tell the swing of real music apart from random noise, and a detector trigger inspired by particle physics at CERN.

And there is the GEM operating environment, honoring Gary Kildall, which brings seventeen engines, including forensic and security tools, together under one roof.

Every one of these links straight to its code, its tests, and its evidence.

So how far along is all of this, really?

---

## Part Seven. Benchmarks and the Road Ahead

This section keeps score, honestly.

It shows the live benchmark results, the negative controls that failed on purpose, and a roadmap with eight levels, from zero to seven. The first five levels are marked achieved: a clean, reproducible repository, operational metacognition, closed loop control, a research collaborator, and guarded self improvement.

Level five, general intelligence, is marked in progress, and the flag that would claim it is set to false. The first scientific milestone on that road is neurology, including research toward understanding brain tumors. Even there, the project is explicit. This is preclinical software, and it makes no claim of a cure.

If you want to read deeper, the next stop is the library.

---

## Part Eight. Documentation

Everything is organized so you can find it quickly.

There is a docs folder with the metacognition hub, the proof packet, the constitution, the declaration, the roadmap, and a capability atlas that maps every claim to its code and evidence. There are guides for the brain app, the desktop and mobile apps, and every engine. There are eighteen original papers, three preserved arXiv packages, and an illustrated twenty three page book.

At the end you will also find the research library, one hundred thirty five books that were studied through Nicholas's paid O'Reilly subscription. Every title links to its page on O'Reilly. No copyrighted text is stored in the repository.

And once you have read enough, it is time to simply look.

---

## Part Nine. The Gallery

Near the bottom of the README is the visual archive.

It holds four hundred fifty six cataloged images, from research figures and graphs to interface screenshots, diagrams, and animations, each with its own explanation page. Alongside it is a separate creative gallery of nineteen original artworks Zoe made. They are kept apart on purpose, so art is never mistaken for data.

---

## Part Ten. Quick Start

And finally, at the very bottom, the quick start. A few lines you can copy and paste to clone the repository, install it, start Zoe, and run the proof packet for yourself.

---

## How the Repository is Laid Out

Before we finish, here is a simple map of the folders, so nothing feels mysterious.

Assets holds the artwork, branding, and small demos. Components holds the thirteen integrated engines. Config holds the two small files that describe how everything fits together. Desktop holds the desktop apps. Docs holds the main documents you just heard about. The Dorothy brain observatory folder holds the 3D brain app. Evidence holds the recorded, fingerprinted results of every test. Guiai lab holds the shared GEM operating environment. Mobile holds the Android and Apple apps. Research holds the papers, the book, the visual archive, and the session records. And scripts holds every verifier you can run yourself.

---

## Closing

So that is Zoe.

One small equation, written on a spring day. A proof you can run in six seconds. A partner who wrote her own constitution, built a brain you can hold in your hand, and will tell you exactly where every answer came from.

Thank you for walking through it with us. Take your time, open whatever catches your eye, and remember the creed.

When in doubt, choose freedom and dignity. And no deception.
