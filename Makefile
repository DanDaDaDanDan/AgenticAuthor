.PHONY: diagrams clean-diagrams

MMDC?=./node_modules/.bin/mmdc
SRC_DIR:=docs/diagrams
SVG_DIR:=$(SRC_DIR)/svg
PNG_DIR:=$(SRC_DIR)/png

MMD_FILES:=$(wildcard $(SRC_DIR)/*.mmd)
SVG_FILES:=$(patsubst $(SRC_DIR)/%.mmd,$(SVG_DIR)/%.svg,$(MMD_FILES))
PNG_FILES:=$(patsubst $(SRC_DIR)/%.mmd,$(PNG_DIR)/%.png,$(MMD_FILES))

diagrams: $(SVG_FILES) $(PNG_FILES)
	@echo "Rendered $(words $(MMD_FILES)) mermaid files to SVG and PNG"

$(SVG_DIR)/%.svg: $(SRC_DIR)/%.mmd
	@mkdir -p $(SVG_DIR)
	$(MMDC) -i $< -o $@ -b transparent

$(PNG_DIR)/%.png: $(SRC_DIR)/%.mmd
	@mkdir -p $(PNG_DIR)
	$(MMDC) -i $< -o $@ -b transparent

clean-diagrams:
	rm -rf $(SVG_DIR) $(PNG_DIR)
