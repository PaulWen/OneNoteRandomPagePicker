from enum import Enum


class OneNoteType(Enum):
    NOTEBOOK = "notebook"
    SECTION_GROUP = "sectionGroup"
    SECTION = "section"
    PAGE = "page"


class OneNoteElement(object):
    def __init__(self, title, autocomplete, uid, subtitle, arg, valid, icon, icontype, onenoteType, oneNoteParent):
      self.title = title
      self.autocomplete = autocomplete
      self.uid = uid
      self.subtitle = subtitle
      self.arg = arg
      self.valid = valid
      self.icon = icon
      self.icontype = icontype
      self.onenoteType = onenoteType
      self.oneNoteParent = oneNoteParent

def as_onenoteelement(data):
    return OneNoteElement(data['title'], data['autocomplete'], data['uid'], data['subtitle'], data['arg'], data['valid'], data['icon'], data['icontype'], data['onenoteType'], data['oneNoteParent'])
