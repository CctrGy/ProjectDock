-- Una regla recibe context y devuelve argumentos. No ejecuta herramientas.
local args = context.args
if context.system == "win32" then
    table.insert(args, "--platform=windows")
else
    table.insert(args, "--platform=unix")
end
return args
