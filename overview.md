We are using an LLM to create a book from high level story premise (LOD3) iterating in every greater detail all the way to LOD0 which is full prose of the book.

LOD levels
- premise + taxonomy (LOD3)
- story treatment (LOD2)
- story broken down into chapters and chapter beats (LOD2)
- full book with prose (LOD0)

As part of the process we need to make sure that the various parts are always in sync.

Structure should be that each book idea is a folder with its own git repository.

Files:
- premise.md (LOD3 - core concept)
- treatment.md (LOD2 - story treatment)
- chapters.yaml (LOD2 - chapter outlines/beats)
- chapters/ folder (LOD0 - prose for each chapter)
  - chapter-01.md
  - chapter-02.md
  - etc.
- summary.md (marketing blurb and metadata)
- project.yaml (metadata and configuration)

LOD.md contains a lot of information on how an existing project located in

D:\Personal\Projects\dv-story-generator

is already doing all this as part of a website.

This project however should be a python based workflow using openrouter API to contact LLMs that acts like a command line interface for iteration along the lines of claude code.