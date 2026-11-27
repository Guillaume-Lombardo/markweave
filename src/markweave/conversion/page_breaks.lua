-- Emit one Word page break for each empty top-level page-break fenced div.
function Pandoc(document)
  for index, block in ipairs(document.blocks) do
    if block.t == "Div" and #block.content == 0 and block.identifier == ""
      and #block.classes == 1 and block.classes[1] == "page-break"
      and #block.attributes == 0 then
      document.blocks[index] = pandoc.RawBlock("openxml",
        '<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    end
  end
  return document
end
