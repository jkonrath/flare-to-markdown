# Flare-to-markdown

    Converts Madcap Flare clean XHTML output to Markdown, suitable for Jekyll.
    
    Jon Konrath (jkonrath@rumored.com)

    You need to do this one-time install:
        python -m pip install pyyaml
    If you're not sure you have these installed:
        python -m pip list

    Warning: this is an incredibly bespoke application and I'm not a good Python developer. I doubt
    this would work out of the box for you, but maybe it's a proof of concept of what you could do.

    This assumes you're in a docs-src directory that has a very specific topic.yml file for TOC that 
    was used for a home-grown Jekyll TOC that you probably don't have.
    This goes through the src/_data/topic.yml and finds any items with flare: true flag set.
