-- Keep one Markdown image reference while selecting print-native PDFs for XeLaTeX.
local thesis_figure_format = "svg"

local function read_metadata(meta)
  if meta.thesisFigureFormat then
    thesis_figure_format = pandoc.utils.stringify(meta.thesisFigureFormat)
  end
  return meta
end

local function select_figure_format(image)
  if thesis_figure_format == "pdf"
      and image.src:match("^figures/.*%.svg$") then
    image.src = image.src:gsub("%.svg$", ".pdf")
  end
  return image
end

-- Separate passes guarantee metadata is available before image traversal.
return {
  { Meta = read_metadata },
  { Image = select_figure_format },
}
