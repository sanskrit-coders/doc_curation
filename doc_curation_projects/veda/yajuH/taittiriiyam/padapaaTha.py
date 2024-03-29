
def get_padasvara(text):
  text = regex.sub('ख्ष', 'क्ष', text)
  text = regex.sub('थ्स', 'त्स', text)
  text = regex.sub('ऱ्', 'र्', text)
  text = regex.sub('ꣴ', 'ं', text)
  text = regex.sub(' इत.*ः', 'ः', text)
  text = regex.sub('॒ इत.*ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]ꣳ', 'ं', text)
  text = regex.sub('ेति[॒॑] .+ा([॒॑]?)$', 'ा\\1', text)
  text = regex.sub('ेति[॒॑] .+([॒॑]?)$', '\\1', text)
  text = regex.sub('ेत्य[॒॑]?.+?([॒॑]?)$', '\\1', text)
  text = regex.sub('ेती[॒॑]?.+?([॒॑]?)$', '\\1', text)
  text = regex.sub('ीति[॒॑] .+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('ीत्य[॒॑]?.+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('ीति[॒॑] .+ि([॒॑]?)$', 'ि\\1', text)
  text = regex.sub('ीत्य[॒॑]?.+ि([॒॑]?)$', 'ि\\1', text)
  text = regex.sub('ा[॒॑]? इत.+ै([॒॑]?)$', 'ै\\1', text)
  text = regex.sub('ी[॒॑]? इत.+ी([॒॑]?)$', 'ी\\1', text)
  text = regex.sub('[॒॑]?दिति[॒॑] .+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?दि[॒॑]?त्य[॒॑]?.+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?दि[॒॑]?ती[॒॑]?.+([॒॑]?)त्$', '\\1त्', text)
  text = regex.sub('[॒॑]?मिति[॒॑] .+?([॑]?)म्$', '\\1म्', text)
  text = regex.sub('[॒॑]?मिति[॒॑] .+?([॑])म्$', '\\1म्', text)
  text = regex.sub('[॒॑]?रिति[॒॑] .+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]?रि[॒॑]?त्य[॒॑]?.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]?रि[॒॑]?ती[॒॑]?.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub('[॒॑]? इ[॒॑]?त.+े([॒॑]?)$', 'े\\1', text)
  text = regex.sub('[॒॑]? इत.+ः([॒॑]?)$', 'ः\\1', text)
  text = regex.sub(' इ॑त.*ः([॒॑]?)', 'ः\\1', text)
  text = regex.sub('्([॒॑])', '्', text)
  text = regex.sub('न्न्([॒॑]?)', 'न्', text)
  text = regex.sub('ं॒ ‌', 'ं', text)
  text = regex.sub(' इति॑$', '<empty-string>', text)
  text = regex.sub('\(३\)', '<empty-string>', text)
  text = regex.sub('ꣳ', 'ँ', text)
  text = regex.sub('([॒॑]?)न्निति[॒॑] .+([॒॑]?)न्', '\\1न्', text)
  text = regex.sub('नि[॒॑]?ति[॒॑]? .*([॒॑]?)न्', 'न्', text)
  text = regex.sub('नि[॒॑]?ती[॒॑]? .*([॒॑]?)न्', 'न्', text)
  text = regex.sub('नि[॒॑]?त्य[॒॑]?.*([॒॑]?)न्', 'न्', text)
  text = regex.sub('मि[॒॑]?ति[॒॑]? .*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('मि[॒॑]?त्य[॒॑]?.*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('मि[॒॑]?ती[॒॑]?.*?([॒॑]?)म्$', '\\1म्', text)
  text = regex.sub('ङि[॒॑]?ति[॒॑]? .*?([॒॑]?)ङ्$', '\\1ङ्', text)
  text = regex.sub('्विति[॒॑] .*ु([॒॑]?)$', 'ु\\1', text)
  text = regex.sub('्वि[॒॑]?त्य[॒॑]?.*ु([॒॑]?)$', 'ु\\1', text)
  text = regex.sub('॒विति॑ .*ो([॒॑]?)$', 'ो\\1', text)
  text = regex.sub('ा[॒॑]?विति[॒॑] .+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?वित्य[॒॑]?.+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?वि[॒॑]?ती[॒॑]?.+ौ([॒॑]?)$', 'ौ\\1', text)
  text = regex.sub('ा[॒॑]?यिति[॒॑] .+ै([॒॑]?)$', 'ै\\1', text)
  text = regex.sub('[॒॑]?गिति[॒॑] .*?([॒॑]?)क्$', '\\1क्', text)
  text = regex.sub('[॒॑]?गि[॒॑]?त्य[॒॑]?.*?([॒॑]?)क्$', '\\1क्', text)
  text = regex.sub('[॒॑]?डिति[॒॑] .*?([॒॑]?)ट्$', '\\1ट्', text)
  text = regex.sub('ू[॒॑]? इत.*ू([॒॑]?)$', 'ू\\1', text)
  text = regex.sub('ो[॒॑]? इ[॒॑]?त.*ो([॒॑]?)$', 'ो\\1', text)
  return text