import Tables as tb
from StructureData import build_structures_lookup
from StructureData import build_structures_list
from StructureData import build_structures_element
from StructureData import define_structure_attributes

from pathlib import Path
import pandas as pd
import xml.etree.ElementTree as ET

#import LoggingConfig as log
#logger = log.logging_init(__name__)

tb.VARIABLE_TYPES = ['Structure', 'Template']
#VERSION = 10.0
VERSION = 13.6

def define_template_attributes():
    '''Create a dictionary with Type Variable values that define all of the template attributes.
    '''
    var_type = 'Template'
    is_string = lambda x: isinstance(x,str)
    id_check = lambda x: is_string(x) and len(x) < 13
    #TODO more attribute checks should be added to the attribute definitions

    template_def = [('Version', None, 1.0), \
                     ('Type', is_string, 'Structure'), \
                     ('ID', id_check, None), \
                     ('Diagnosis', is_string, ''), \
                     ('TreatmentSite', is_string, '.All'), \
                     ('AssignedUsersID', is_string, 'gsal;'), \
                     ('Description', is_string, ''), \
                     ('ApprovalStatus', is_string, 'Unapproved'), \
                     ('ApprovalHistory', is_string, ''), \
                     ('LastModified', is_string, '')]
    return  {ID: tb.Variable(ID, var_type, validate=val, default=dflt)
                              for (ID, val, dflt) in template_def}

def define_template_tables(file_path: Path, sheet_name: str, \
            tmpl_title: str, tmpl_offset='A1', tmpl_columns=2, \
            struc_title='Template Structures', struc_offset='D1', struc_columns=5):
    '''Create Table definitions for the template table and
    it's companion structure list required to build a structure template.
    '''
    #TODO define_template_tables is getting messy probably should get rid of it
    # values for all tables
    tmp_index = 'Attribute'
    str_index = 'ID'
    # Rows is not yet implemented not using
    template_table = tb.Table(file_path, sheet_name, tmpl_title, tmp_index, tmpl_offset, columns=tmpl_columns)
    structures_dfn = define_structure_attributes()
    structures_table = tb.Table(file_path, sheet_name, struc_title, str_index, struc_offset, struc_columns, variables=structures_dfn)

    return  (template_table, structures_table)

def build_template_data(template_table: tb.Table):
    '''Create a dictionary of template data from template_table and the default template_attributes.
    '''
    template_attributes = define_template_attributes()
    template_data = template_table.read_table()
    # Transpose table so that each attribute becomes a column
    template_data = template_data.T.reset_index(drop=True)
    #TODO Select and validate attributes in this table
    template_data = tb.insert_defaults(template_data, template_attributes)
    template_data = tb.insert_missing_variables(template_data, template_attributes)
    #Only one template definition per table, so select the first row from the DataFrame
    return dict(template_data.iloc[0,:])

def list_of_structures(structures, begin_text=None, sort_IDs=True):
    '''Assemble a text string that includes the begin_text (or default) and a
    comma separated list of all structure IDs in the structures DataFrame
    The structures are sorted alphabetically by default.
    '''
    default_text = '\u000aStructures Included: '
    if begin_text is None:
        begin_text = default_text
    structure_IDs = list(structures['ID'])
    if sort_IDs:
        structure_IDs.sort()
    struct_list = ', '.join(structure_IDs)
    struct_summary = begin_text + struct_list
    return struct_summary

def add_preview(template, template_data):
    '''Add a the preview element to the template tree using the data in template_data.
    '''
    type = tb.get_value(template_data, 'Type')
    site = tb.get_value(template_data, 'TreatmentSite')
    diagnosis = tb.get_value(template_data, 'Diagnosis')
    description = tb.get_value(template_data, 'Description')
    users = tb.get_value(template_data, 'AssignedUsers')
    status = tb.get_value(template_data, 'ApprovalStatus')
    history = tb.get_value(template_data, 'ApprovalHistory')
    modified = tb.get_value(template_data, 'LastModified')

    preview = ET.SubElement(template, 'Preview ', \
        attrib={'ID':template_data['ID'], \
                'Type':type, \
                'TreatmentSite':site, \
                'Diagnosis':diagnosis, \
                'Description':description, \
                'AssignedUsers':users, \
                'ApprovalStatus':status, \
                'ApprovalHistory':history, \
                'LastModified':modified})

    return preview

def make_template(template_data, structures, template_file: Path):
    '''Create a template XML from template and structure data.
    '''
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')

    if VERSION == 13.6:
        template = ET.Element('StructureTemplate',attrib={'Version':'1.1',
                    'xmlns:xsi':"http://www.w3.org/2001/XMLSchema-instance"})
    elif VERSION == 10.0:
        template = ET.Element('StructureTemplate',attrib={'Version':'1.0',
                    'xmlns:xsi':"http://www.w3.org/2001/XMLSchema-instance"})
    else:
        raise ValueError('{} is an invalid version.'.format(VERSION))

    add_preview(template, template_data)
    structure_set = build_structures_element(structures, VERSION)
    template.append(structure_set)
    template_tree = ET.ElementTree(template)
    template_tree.write(str(template_file), encoding='UTF-8', xml_declaration=True, short_empty_elements=False)

def build_templates(template_list, base_path, structures_lookup, include_structure_list=False):
    '''Build a collection of structure template files from the list of templates
    in template_list that describe template data in the template file. Structure
    data used for the templates comes from the structures_lookup data-frame.
    '''
    all_structure_data = pd.DataFrame()
    for tmpl in  template_list:
        print('Building Template: %s' %tmpl['title'])
        template_file_path = base_path / tmpl['workbook_name']
        (template_table, structures_table) = define_template_tables(template_file_path, \
                                                                    sheet_name=tmpl['sheet_name'], \
                                                                    tmpl_title= tmpl['title'], \
                                                                    struc_columns=tmpl['columns'])
        #Load the template and structure data from the excel worksheet
        template_data = build_template_data(template_table)
        structures = build_structures_list(structures_table, structures_lookup)
        #Create and return a summary of the template structures
        structure_data = structures
        structure_data['Template'] = template_data['ID']
        structure_data['TreatmentSite'] = template_data['TreatmentSite']
        structure_data['TemplateType'] = template_data['Type']
        structure_data['TemplateDescription'] = template_data['Description']
        if include_structure_list:
            #Add list of structures to the template description
            struct_summary = list_of_structures(structures)
            description = template_data['Description'] + struct_summary
            template_data['Description'] = description
        # convert the template and structure data to an XML file
        template_save_file = base_path / tmpl['output_file_name']
        template_tree = make_template(template_data, structures, template_save_file)
        all_structure_data = all_structure_data.append(structure_data, ignore_index=True)
    return all_structure_data

if __name__ == '__main__':
    #base_path = Path(r'C:\Users\gsalomon\OneDrive for Business 1\Structure Dictionary')
    base_path = Path(r'C:\Users\gsalomon\OneDrive for Business 1\Structure Dictionary\Templates\New Templates\V13')
    #base_path = Path(r"C:\Users\Greg\OneDrive - Queen's University\Structure Dictionary")
    base_path = Path(r"C:\Users\Greg\OneDrive - Queen's University\Structure Dictionary\Templates\New Templates\V13")
    structures_lookup_file_name = 'Structure Lookup.xlsx'
    structures_file_path = base_path / structures_lookup_file_name
    structures_lookup = build_structures_lookup(structures_file_path)
    templates_list = [ \
        {'workbook_name': 'Specialty Templates.xlsx', 'sheet_name': 'Artifact', 'title': 'Artifact', 'file_name': 'Artifact.xml', 'columns': 5}, \
        {'workbook_name': 'Basic Templates.xlsx', 'sheet_name': 'CT', 'title': 'CT', 'file_name': 'CT Template.xml', 'columns': 3}]
    structure_data = build_templates(templates_list, base_path, structures_lookup, include_structure_list=True)
    structures_file_name = base_path / 'Structure data.txt'
    structure_data.to_csv(str(structures_file_name), sep=';', index=False)
