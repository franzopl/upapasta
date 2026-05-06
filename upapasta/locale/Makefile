DOMAIN   = upapasta
SRC_DIR  = ../upapasta
POT      = $(DOMAIN).pot
LANGS    = en pt_BR

.PHONY: extract init compile update clean

# Extract translatable strings from source
extract:
	xgettext --language=Python --keyword=_ \
	    --output=$(POT) \
	    --package-name=$(DOMAIN) \
	    --from-code=UTF-8 \
	    $(SRC_DIR)/*.py

# Initialise a new language (usage: make init LANG=es)
init: extract
	@test -n "$(LANG)" || (echo "Usage: make init LANG=<code>"; exit 1)
	mkdir -p $(LANG)/LC_MESSAGES
	msginit --no-translator --input=$(POT) --locale=$(LANG) \
	    --output=$(LANG)/LC_MESSAGES/$(DOMAIN).po

# Compile all .po → .mo
compile:
	@for lang in $(LANGS); do \
	    msgfmt $$lang/LC_MESSAGES/$(DOMAIN).po \
	           -o $$lang/LC_MESSAGES/$(DOMAIN).mo \
	    && echo "compiled $$lang"; \
	done

# Merge new strings from POT into existing .po files
update: extract
	@for lang in $(LANGS); do \
	    msgmerge --update --backup=none \
	        $$lang/LC_MESSAGES/$(DOMAIN).po $(POT) \
	    && echo "updated $$lang"; \
	done

clean:
	rm -f $(POT)
	@for lang in $(LANGS); do rm -f $$lang/LC_MESSAGES/$(DOMAIN).mo; done
