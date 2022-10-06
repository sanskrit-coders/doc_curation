<xsl:stylesheet
        version="2.0"
        xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
        xmlns:tei="http://www.tei-c.org/ns/1.0"
        xpath-default-namespace="http://www.tei-c.org/ns/1.0">

    <xsl:import href="tei-to-markdown-sarit.xsl"/>
    <xsl:template match="div[@type='chapter']">
        <xsl:call-template name="newline"/>
        <xsl:text>## </xsl:text>
        <xsl:value-of select="@n"/>
        <xsl:call-template name="newline"/>
        <xsl:apply-templates/>
    </xsl:template>
    <xsl:template match="head">
        <xsl:call-template name="newline"/>
        <xsl:text><![CDATA[<details><summary>{{Summary (SA)}}</summary>]]></xsl:text>
        <xsl:call-template name="newline"/>
        <xsl:call-template name="newline"/>
        <xsl:text>{{</xsl:text>
        <xsl:apply-templates/>
        <xsl:text>}}</xsl:text>
        <xsl:call-template name="newline"/>
        <xsl:text><![CDATA[</details>]]></xsl:text>
    </xsl:template>
    <xsl:template match="note[@place='margin']">
        <xsl:call-template name="newline"/>
        <xsl:call-template name="newline"/>
        <xsl:text>{{Ref: </xsl:text>
        <xsl:apply-templates/>
        <xsl:text>}}</xsl:text>
        <xsl:call-template name="newline"/>
    </xsl:template>
    <xsl:template match="label">
    </xsl:template>
</xsl:stylesheet>
