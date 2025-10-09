# Export and Publishing Guide

Complete guide to exporting your book and preparing it for Amazon Kindle Direct Publishing (KDP).

---

## Overview

This guide covers the complete workflow from finishing your manuscript in AgenticAuthor to publishing on Amazon KDP and other platforms.

---

## Step 1: Complete Your Manuscript

### Generate All Content

```bash
/open my-novel
/generate premise
/generate treatment
/generate chapters
/generate prose all
```

### Review and Iterate

```bash
/iterate prose          # Make improvements to chapters
/analyze                # Check for plot holes, character consistency
```

---

## Step 2: Set Book Metadata

### Minimum Required Metadata

```bash
/metadata title "Your Book Title"
/metadata author "Your Name"
/metadata copyright 2025
```

These three fields are all you need to export.

### Metadata Details

- **Title**: Your book's title (required for export)
- **Author**: Your name or pen name (required for export)
- **Copyright Year**: Defaults to current year if not set

---

## Step 3: Export Your Book

### Export to RTF (for Kindle/ebook)

```bash
/export rtf
```

This creates: `books/your-novel/exports/your-book-title.rtf`

**RTF export includes**:
- Professional title page
- Copyright page with legal text
- Frontmatter sections (from `frontmatter.md`)
- All chapters with proper formatting
- First-line paragraph indents (0.25")
- Justified text
- Scene breaks
- No duplicate chapter headings

### Export to Markdown (for reference)

```bash
/export markdown
```

This creates: `books/your-novel/exports/your-book-title.md`

**Markdown export includes**:
- Combined single file with all content
- Title page
- Copyright section
- Frontmatter
- All chapters

---

## Step 4: Customize Frontmatter (Optional)

Your book's `frontmatter.md` file contains sections that appear before Chapter 1:

### Default Sections

1. **Title Page** - Title and author (automatically filled)
2. **Copyright Page** - Legal text (automatically filled)
3. **Dedication** - Add your dedication text or delete section
4. **Acknowledgments** - Thank your supporters or delete section

### How to Customize

1. Open `books/your-novel/frontmatter.md` in any text editor
2. Edit the dedication and acknowledgments sections
3. Add additional sections if desired (e.g., "About the Series", "Content Warning")
4. Use `{{title}}`, `{{author}}`, `{{copyright_year}}` for automatic variable replacement
5. Delete sections you don't want (just remove the entire `## Section Name` block)

### Example Custom Frontmatter

```markdown
---
## Title Page

{{title}}

by {{author}}

---

## Copyright

Copyright © {{copyright_year}} by {{author}}

All rights reserved...

---

## Dedication

For my family, who believed in this story from the beginning.

---

## Content Warning

This book contains themes of violence and loss that some readers may find disturbing.

---

## About the Series

This is Book 1 in the Shadow Protocol series. Each book can be read standalone,
but the series is best enjoyed in order.
```

---

## Step 5: Prepare Publishing Metadata

### What is Publishing Metadata?

Beyond your book's content (the RTF file), Amazon KDP requires additional information:

- **Book Description** (your sales pitch, up to 4,000 characters)
- **Keywords** (7 boxes of search terms, 50 characters each)
- **Categories** (up to 3 categories for your book)
- **Author Bio** (100-200 words about you)
- **Pricing** (your book's price and royalty choice)
- **Territories** (where your book can be sold)

### Use the Publishing Metadata Template

We've created a comprehensive template to help you prepare all this information:

**Location**: `docs/PUBLISHING_METADATA_TEMPLATE.md`

**What's included**:
1. Core book information (title, author, series)
2. Book description (4,000-character sales copy)
3. Keywords (7 boxes with research guidance)
4. Categories (3 categories with strategy notes)
5. Author bio (with examples)
6. Comparable titles (comp titles)
7. Pricing strategy
8. Territory and rights management
9. Content declarations
10. Marketing and launch checklist

### How to Use the Template

1. **Copy the template** to your project:
   ```bash
   cp docs/PUBLISHING_METADATA_TEMPLATE.md books/your-novel/publishing-metadata.md
   ```

2. **Fill out each section** with your book's specific information

3. **Use the research guide** (`docs/KINDLE_PUBLISHING_METADATA_RESEARCH.md`) for detailed best practices on:
   - Writing compelling book descriptions
   - Choosing effective keywords
   - Selecting optimal categories
   - Crafting author bios
   - Pricing strategies

---

## Step 6: Write Your Book Description

Your book description is **the most important piece of marketing copy** you'll write. It's your sales pitch.

### Book Description Best Practices

**Character Limit**: 4,000 characters maximum
**Optimal Length**: 100-150 words (~500-750 characters)
**Key Principle**: Be compelling and scannable, not exhaustive

**Structure for Fiction**:

1. **Hook** (1-2 sentences)
   - Grab attention immediately
   - Set tone and genre
   - Example: "She has one week to find her sister's killer—or become the next victim."

2. **Main Conflict** (2 paragraphs)
   - Introduce protagonist
   - Present central conflict
   - Raise emotional stakes
   - Don't spoil the ending!

3. **Call to Action**
   - Simple ending encouraging purchase
   - "Discover...", "Experience...", "Join [character] on..."

**Structure for Nonfiction**:

1. **Problem Statement**
   - Identify reader's pain point
   - Make them feel understood

2. **Your Solution**
   - Position your book as the answer
   - Focus on benefits

3. **Credentials**
   - Establish your authority
   - Why you're qualified

4. **Call to Action**
   - Encourage transformation

### Formatting Your Description

Use HTML tags for formatting:

```html
<b>Bold text for hooks and key phrases</b>
<i>Italic text for emphasis or book titles</i>
<br> for line breaks
<p>For paragraph breaks</p>
```

### What NOT to Include

- Reviews or testimonials (forbidden as of May 2024)
- Contact information
- Time-sensitive information
- Spoilers
- Unicode emojis

### Examples

**Fiction Example**:
```html
<b>In a world where memories can be stolen, one thief refuses to forget.</b><br><br>

Kira has made a living stealing memories from the wealthy—until the night she's
hired to extract a memory that doesn't exist. Now she's on the run from the most
powerful family in New Atlanta, hunted by memory traders who want to erase everything
she knows.<br><br>

Her only ally is Marcus, a rogue detective with secrets of his own. Together they
must uncover the truth behind the impossible memory before Kira's own past is
rewritten forever.<br><br>

But in a city built on lies and forgotten truths, remembering might be the most
dangerous choice of all.<br><br>

<b>A thrilling blend of cyberpunk action and emotional depth, perfect for fans of
<i>Altered Carbon</i> and <i>The Quantum Thief</i>.</b>
```

**Nonfiction Example**:
```html
<b>Are you struggling to finish your novel?</b><br><br>

You're not alone. Most aspiring authors start with passion but get lost in the
complexity of plot, character development, and structure.<br><br>

<i>The Complete Guide to Novel Writing</i> provides a proven step-by-step system
that takes you from blank page to finished manuscript. Inside, you'll discover:<br><br>

• How to craft compelling characters readers can't forget<br>
• The secret to plot structure that keeps pages turning<br>
• Editing techniques used by bestselling authors<br>
• Common mistakes that sink manuscripts—and how to avoid them<br><br>

Drawing on 20 years of experience as a developmental editor and published author,
Jane Smith breaks down the novel-writing process into manageable, actionable steps.<br><br>

<b>Stop dreaming about writing. Start finishing.</b>
```

---

## Step 7: Research Keywords

Keywords are how readers find your book through Amazon search.

### The Basics

- You get **7 keyword boxes**
- Each box holds up to **50 characters**
- Can be single words or 2-3 word phrases
- Keywords are **not visible** to customers

### How to Research Keywords

**Method 1: Amazon Autocomplete**
1. Go to Amazon.com
2. Type your genre or topic in search bar
3. Note the autocomplete suggestions
4. Those are real searches from real readers!

**Method 2: Check Competitors**
1. Find successful books similar to yours
2. Check their categories
3. Use tools like Publisher Rocket (paid) to see what keywords work

**Method 3: Think Like a Reader**
- What would someone type to find YOUR book?
- Be specific: "space opera romance" beats "science fiction"
- Include subgenres, tropes, themes

### Example Keywords (Urban Fantasy Romance)

```
Box 1: urban fantasy romance paranormal
Box 2: witches magic supernatural thriller
Box 3: strong female protagonist fantasy
Box 4: dark fantasy urban setting
Box 5: enemies to lovers paranormal romance
Box 6: fast paced action adventure fantasy
Box 7: magical realism contemporary fantasy
```

### What to Avoid

- Don't use quotes (limits to exact phrase match)
- Don't repeat keywords across boxes
- Don't include your title or author name
- Don't use category names
- Don't use Amazon program names (Kindle Unlimited, KDP Select)

---

## Step 8: Choose Categories

Categories are how readers browse to find books like yours.

### The Basics

- Choose up to **3 categories**
- Be as **specific** as possible
- Must accurately reflect your book's content

### How to Find Good Categories

**Method 1: Check Bestsellers**
1. Search for books similar to yours
2. Click on a successful book
3. Scroll down to "Amazon Best Sellers Rank"
4. See what categories it's ranked in
5. If your book fits there, use those categories

**Method 2: Browse Amazon**
1. Go to Amazon.com
2. Browse Books → [Your Genre] → [Subgenres]
3. Find the most specific category that fits your book

### Category Strategy

**Option 1: Broad Reach**
- Choose 3 different category paths
- Maximizes visibility

**Option 2: Niche Domination**
- Choose 3 very specific subcategories
- Easier to become "bestseller" in niche

**Option 3: Hybrid**
- 1 broad category for visibility
- 2 specific subcategories for bestseller badges

### Example Categories (Science Fiction)

```
Category 1: Books > Science Fiction & Fantasy > Science Fiction > Space Opera
Category 2: Books > Science Fiction & Fantasy > Science Fiction > Military
Category 3: Kindle Store > Kindle eBooks > Science Fiction > Adventure
```

---

## Step 9: Set Your Price

### Royalty Options

**70% Royalty**:
- Price between **$2.99 - $9.99**
- Highest earnings per sale
- Best for most fiction

**35% Royalty**:
- Any price (including $0.99 or $10+)
- Lower earnings per sale
- Use for loss leaders or premium nonfiction

### Common Price Points

- **$0.99** - Loss leader, series starter, promotion
- **$2.99-$4.99** - Most fiction sweet spot
- **$5.99-$7.99** - Longer fiction, established authors
- **$8.99-$9.99** - Maximum 70% royalty
- **$10+** - Premium nonfiction (35% royalty)

### Pricing Strategy

Consider:
- **Your genre's typical prices** (research on Amazon)
- **Your book's length**
- **Your author platform** (unknown vs. established)
- **Series strategy** (price Book 1 lower to hook readers)

---

## Step 10: Create Your Author Bio

### Purpose

- Establish credibility (especially for nonfiction)
- Help readers connect with you
- Encourage them to follow you and read more

### Length

- **Optimal**: 100-200 words
- Keep it concise but informative

### What to Include

**For Fiction Authors**:
- Writing style or themes you explore
- Previous publications (if any)
- Awards or recognition
- Brief personal detail (location, hobbies)
- Where readers can find you (website, social media)

**For Nonfiction Authors**:
- Professional credentials
- Expertise and authority on subject
- Previous publications
- Why you're qualified to write this book
- Personal connection to topic

### Example Author Bio (Fiction)

> Jane Smith writes science fiction novels that explore themes of identity and
> technology's impact on humanity. Her debut novel *Echoes of Tomorrow* was a
> finalist for the Nebula Award and has been praised by Locus Magazine as
> "a stunning meditation on what makes us human." When not writing, Jane works
> as a software engineer and lives in Seattle with her husband and two rescue dogs.
> Visit her website at janesmith.com for news about upcoming releases.

### Example Author Bio (Nonfiction)

> John Davis is a licensed psychologist with over 15 years of experience treating
> anxiety disorders. He has published research in the Journal of Clinical Psychology
> and regularly contributes to Psychology Today. John's expertise in cognitive
> behavioral therapy stems from his own journey overcoming panic disorder in his
> twenties. He holds a Ph.D. from Stanford University and currently maintains a
> private practice in Austin, Texas. Learn more at drjohndavis.com.

---

## Step 11: Upload to Amazon KDP

### Before You Upload

**Checklist**:
- [ ] RTF file exported and reviewed
- [ ] Frontmatter customized
- [ ] Book description written (4,000 characters)
- [ ] All 7 keyword boxes filled
- [ ] 3 categories selected
- [ ] Author bio written
- [ ] Price determined
- [ ] Cover design ready (1600x2560 minimum)

### Upload Process

1. **Go to KDP**: https://kdp.amazon.com
2. **Create Account** (if first time)
3. **Click "Create New Title"**
4. **Fill in ALL metadata fields**:
   - Title, author, description
   - Keywords, categories
   - Territory rights
   - Pricing
5. **Upload your RTF file**
6. **Upload your cover image**
7. **Preview your book** (Kindle Previewer)
8. **Publish**

### After Publishing

- Your book typically goes live within **24-72 hours**
- You'll receive an email when it's live
- Link appears in your KDP dashboard

---

## Step 12: Market Your Book

### Launch Week

**Free Marketing**:
- Announce on social media
- Email your mailing list
- Post in genre-specific Facebook groups
- Share on Reddit (r/books, genre subreddits)
- Update your author website
- Tell friends and family

**Paid Marketing**:
- Amazon Ads (start small, $5/day)
- Facebook/Instagram ads
- BookBub Featured Deal (very competitive)
- Newsletter services (Written Word Media, Robin Reads)

### Ask for Reviews

- Email your ARC (Advanced Review Copy) team
- Add note in back matter: "If you enjoyed this book, please consider leaving a review"
- Join review groups (carefully, follow rules)
- **Never** buy fake reviews (against Amazon TOS)

### Track Performance

Monitor:
- **Sales Rank** (Amazon Best Sellers Rank)
- **Category Rankings** (top 20 is great!)
- **Reviews** (quantity and quality)
- **Page Reads** (if in KDP Select)

### Adjust as Needed

After 30 days:
- Review your keywords (are they working?)
- Consider changing categories
- Test different prices
- Revise description if needed

---

## Tools & Resources

### Free Tools

- **Amazon Search Autocomplete** - Keyword research
- **Amazon Bestseller Lists** - Category research
- **Goodreads** - Author profile, connect with readers
- **Kindle Previewer** - Preview how your book looks on devices
- **Canva** - Create social media graphics (free tier)

### Paid Tools

- **Publisher Rocket** ($97 one-time) - Keyword and category research
- **Atticus** ($147 one-time) - Formatting and design
- **Vellum** ($249 Mac only) - Beautiful formatting
- **BookBrush** ($10/month) - Marketing graphics

### Educational Resources

- **KDP University** - kdp.amazon.com/help
- **Reedsy Blog** - blog.reedsy.com
- **Jane Friedman** - janefriedman.com
- **Kindlepreneur** - kindlepreneur.com
- **Alliance of Independent Authors** - allianceindependentauthors.org

---

## Troubleshooting

### Common Issues

**Q: My book isn't showing up in my chosen categories**
- A: Make sure categories accurately reflect content. Try different categories. Use keywords to reinforce categories.

**Q: I'm not getting sales**
- A: Check your cover (is it professional and genre-appropriate?), description (is it compelling?), keywords (are they specific enough?), and price (is it competitive?).

**Q: How do I get more reviews?**
- A: Build an ARC team, email your list, include note in back matter. Be patient—reviews take time.

**Q: Should I use KDP Select (exclusive to Amazon)?**
- A: Try it for the first 90 days. If Kindle Unlimited reads are strong, stay in. If not, go wide (distribute on other platforms).

**Q: My formatting looks wrong on Kindle devices**
- A: Use Kindle Previewer to check all devices. RTF is usually safe, but complex formatting can cause issues. Consider professional formatting.

---

## Next Steps

After your first book is published:

1. **Start your next book** - The best marketing is more books
2. **Build your mailing list** - Direct connection with readers
3. **Engage on social media** - Build your author brand
4. **Join author communities** - Learn from others (Facebook groups, Reddit r/selfpublish)
5. **Keep learning** - Publishing is always evolving

---

## Summary: The Export to Publishing Workflow

1. ✅ Complete manuscript in AgenticAuthor
2. ✅ Set metadata (`/metadata title`, `/metadata author`)
3. ✅ Export to RTF (`/export rtf`)
4. ✅ Customize frontmatter.md (optional)
5. ✅ Fill out publishing metadata template
6. ✅ Write book description (4,000 characters)
7. ✅ Research and select keywords (7 boxes)
8. ✅ Choose categories (3 categories)
9. ✅ Write author bio (100-200 words)
10. ✅ Set price and territories
11. ✅ Upload to KDP with cover
12. ✅ Market and monitor performance

**Good luck with your launch!** 🚀📚

---

## Document Version

- **Version**: 1.0
- **Last Updated**: 2025-01-09
- **Next Review**: As KDP policies change
