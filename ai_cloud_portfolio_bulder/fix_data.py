with open('app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if 'data = {' in line:
        new_lines.append(line)
        new_lines.append('\n')
        new_lines.append('            "user_email": session["user"],\n')
        new_lines.append('            "name": name,\n')
        new_lines.append('            "role": role,\n')
        new_lines.append('            "intro": intro,\n')
        new_lines.append('            "education": education,\n')
        new_lines.append('            "skills": skills,\n')
        new_lines.append('            "template": request.form.get("template", "standard"),\n')
        new_lines.append('            "projects":[\n')
        new_lines.append('                project1,\n')
        new_lines.append('                project2,\n')
        new_lines.append('                project3\n')
        new_lines.append('            ],\n')
        new_lines.append('            "certifications":[\n')
        new_lines.append('                {"image": cert_img1_name},\n')
        new_lines.append('                {"image": cert_img2_name},\n')
        new_lines.append('                {"image": cert_img3_name}\n')
        new_lines.append('            ],\n')
        new_lines.append('            "resume": resume_filename,\n')
        new_lines.append('            "email": email,\n')
        new_lines.append('            "phone": phone,\n')
        new_lines.append('            "linkedin": linkedin,\n')
        new_lines.append('            "github": github,\n')
        new_lines.append('            "photo": filename,\n')
        new_lines.append('        }\n')
        skip = True
    elif skip and 'portfolio_collection.update_one' in line:
        new_lines.append('\n')
        new_lines.append(line)
        skip = False
    elif not skip:
        new_lines.append(line)

with open('app.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)
